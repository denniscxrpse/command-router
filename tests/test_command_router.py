from __future__ import annotations

import http.client
import threading
from pathlib import Path

import pytest

import cmd_router as command_router_module
from cmd_router import CommandRouter
from cmd_router.utils.cli import flags
from cmd_router.utils.context import error, paths


def _json_grammar(command: str = "say") -> str:
    return (
        "{\n"
        '  "cmd-router": {\n'
        '    "schema-version": 1,\n'
        f'    "grammar": {{"{command}": "<message...>"}}\n'
        "  }\n"
        "}\n"
    )


def _toml_grammar(command: str = "say") -> str:
    return f'[cmd-router]\nschema-version = 1\n\n[cmd-router.grammar]\n{command} = "<message...>"\n'


@pytest.fixture
def router() -> CommandRouter:
    instance = CommandRouter.__new__(CommandRouter)
    instance._grammars = {}
    instance._info = {}
    return instance


def test_normalize_merges_grammar_and_info(router: CommandRouter) -> None:
    router._normalize(({"say": "<message...>"}, {"schema-version": 1}))

    assert router._grammars == {"say": "<message...>"}
    assert router._info == {"schema-version": 1}


def test_default_ignore_contains_one_filename() -> None:
    assert flags.ignore == frozenset({"err.json5"})


def test_constructor_loads_non_lazy_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grammar = tmp_path / "grammar.json5"
    grammar.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(paths, "FIXTURES", tmp_path)
    monkeypatch.setattr(flags, "lazy", False)
    monkeypatch.setattr(CommandRouter, "_grammars", {})
    monkeypatch.setattr(CommandRouter, "_info", {})

    router = CommandRouter()

    assert router._grammars == {"say": "<message...>"}
    assert router._info == {"schema-version": 1}


def test_init_grammar_loads_supported_files_and_skips_unknown_files(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_file = tmp_path / "grammar.json5"
    toml_file = tmp_path / "grammar.toml"
    text_file = tmp_path / "notes.txt"
    json_file.write_text(_json_grammar("json"), encoding="utf-8")
    toml_file.write_text(_toml_grammar("toml"), encoding="utf-8")
    text_file.write_text("not a grammar", encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset())

    result = router._init_grammar([json_file, toml_file, text_file])

    assert result == (
        {"json": "<message...>", "toml": "<message...>"},
        {"schema-version": 1},
    )


def test_init_grammar_ignores_a_filename(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = tmp_path / "ignored.json5"
    included = tmp_path / "included.json5"
    ignored.write_text("invalid", encoding="utf-8")
    included.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({ignored.name}))

    result = router._init_grammar([ignored, included])

    assert result == ({"say": "<message...>"}, {"schema-version": 1})


def test_init_grammar_ignores_a_full_file_path(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = tmp_path / "ignored.json5"
    included = tmp_path / "included.json5"
    ignored.write_text("invalid", encoding="utf-8")
    included.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({str(ignored)}))

    result = router._init_grammar([ignored, included])

    assert result == ({"say": "<message...>"}, {"schema-version": 1})


def test_init_grammar_ignores_files_under_a_directory(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    ignored = ignored_dir / "ignored.json5"
    included = tmp_path / "included.json5"
    ignored.write_text("invalid", encoding="utf-8")
    included.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({str(ignored_dir)}))

    result = router._init_grammar([ignored, included])

    assert result == ({"say": "<message...>"}, {"schema-version": 1})


def test_init_grammar_returns_validation_error(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = tmp_path / "invalid.json5"
    invalid.write_text(_json_grammar().replace('"schema-version": 1', '"schema-version": -1'), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset())

    result = router._init_grammar(invalid)

    assert result == error.Abort


def _post_to_lazy_router(
    monkeypatch: pytest.MonkeyPatch,
    router: CommandRouter,
    payloads: list[bytes],
    fixture_root: Path,
) -> list[int]:
    ready = threading.Event()
    servers: list[command_router_module.HTTPServer] = []
    errors: list[BaseException] = []
    real_server = command_router_module.HTTPServer

    class _RecordingHTTPServer(real_server):
        def __init__(self, *args: object, **kwargs: object) -> None:
            # pyrefly: ignore [bad-argument-type]
            super().__init__(*args, **kwargs)
            servers.append(self)
            ready.set()

    monkeypatch.setattr(command_router_module, "HTTPServer", _RecordingHTTPServer)
    monkeypatch.setattr(paths, "FIXTURES", fixture_root)

    def serve() -> None:
        try:
            router._lazy_init()
        except BaseException as exception:  # pragma: no cover - surfaced by the assertion below
            errors.append(exception)

    thread = threading.Thread(target=serve)
    thread.start()
    assert ready.wait(timeout=2), errors
    server = servers[0]
    statuses: list[int] = []
    for payload in payloads:
        # pyrefly: ignore [bad-argument-type]
        connection = http.client.HTTPConnection(*server.server_address, timeout=2)
        connection.request("POST", "/", body=payload)
        response = connection.getresponse()
        statuses.append(response.status)
        response.read()
        connection.close()

    thread.join(timeout=2)
    assert not thread.is_alive()
    assert not errors
    return statuses


@pytest.mark.parametrize(
    ("grammar", "extension"),
    [(_json_grammar(), ".json5"), (_toml_grammar(), ".toml")],
)
def test_lazy_init_reuses_an_identical_persisted_grammar(
    grammar: str, extension: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = grammar.encode()
    first = CommandRouter.__new__(CommandRouter)
    first._grammars = {}
    first._info = {}
    second = CommandRouter.__new__(CommandRouter)
    second._grammars = {}
    second._info = {}

    assert _post_to_lazy_router(monkeypatch, first, [payload], tmp_path) == [204]
    assert _post_to_lazy_router(monkeypatch, second, [payload], tmp_path) == [204]
    assert len(list((tmp_path / "http").glob(f"grammar-*{extension}"))) == 1
    assert second._grammars == {"say": "<message...>"}
    assert second._info == {"schema-version": 1}
