import http.client
import threading
from pathlib import Path

import pytest

import cmd_router as command_router_module
from cmd_router import CommandRouter
from cmd_router.utils.cli import flags
from cmd_router.utils.context import error, paths, uctx_k

CMD_ROUTER = uctx_k.cmd_router
SCHEMA_VERSION = uctx_k.schema_version
GRAMMAR = uctx_k.grammar


def _json_grammar(command: str = "say") -> str:
    return "{" f'"{CMD_ROUTER}":' "{" f'"{SCHEMA_VERSION}": 1,' f'"{GRAMMAR}":{{"{command}": "<message...>"}}' "}}"


def _toml_grammar(command: str = "say") -> str:
    return f'[{CMD_ROUTER}]\n{SCHEMA_VERSION}=1\n[{CMD_ROUTER}.{GRAMMAR}]\n{command}="<message...>"'


GRAMMAR_JSON5 = "grammar.json5"
GRAMMAR_TOML = "grammar.toml"
GRAMMAR_TXT = "notes.txt"
GRAMMAR_ERR = "err.json5"

GRAMMAR_IGNORED = "ignored.json5"
GRAMMAR_INCLUDE = "include.json5"
GRAMMAR_INVALID = "invalid.json5"


@pytest.fixture
def router() -> CommandRouter:
    instance = CommandRouter.__new__(CommandRouter)
    instance._grammars = {}
    instance._info = {}
    return instance


def test_normalize_merges_grammar_and_info(router: CommandRouter) -> None:
    router._normalize(({"say": "<message...>"}, {SCHEMA_VERSION: 1}))

    assert router._grammars == {"say": "<message...>"}
    assert router._info == {SCHEMA_VERSION: 1}


def test_default_ignore_contains_one_filename() -> None:
    assert flags.ignore == frozenset({GRAMMAR_ERR})


def test_constructor_loads_non_lazy_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grammar = tmp_path / GRAMMAR_JSON5
    grammar.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(paths, "FIXTURES", tmp_path)
    monkeypatch.setattr(flags, "lazy", False)
    monkeypatch.setattr(CommandRouter, "_grammars", {})
    monkeypatch.setattr(CommandRouter, "_info", {})

    router = CommandRouter()

    assert router._grammars == {"say": "<message...>"}
    assert router._info == {SCHEMA_VERSION: 1}


def test_init_grammar_loads_supported_files_and_skips_unknown_files(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_file = tmp_path / GRAMMAR_JSON5
    toml_file = tmp_path / GRAMMAR_TOML
    text_file = tmp_path / GRAMMAR_TXT
    json_file.write_text(_json_grammar("json"), encoding="utf-8")
    toml_file.write_text(_toml_grammar("toml"), encoding="utf-8")
    text_file.write_text("not a grammar", encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset())

    result = router._grammar_init([json_file, toml_file, text_file])

    assert result == (
        {"json": "<message...>", "toml": "<message...>"},
        {SCHEMA_VERSION: 1},
    )


def test_init_grammar_ignores_a_filename(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = tmp_path / GRAMMAR_IGNORED
    include = tmp_path / GRAMMAR_INCLUDE
    ignored.write_text("invalid", encoding="utf-8")
    include.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({ignored.name}))

    result = router._grammar_init([ignored, include])

    assert result == ({"say": "<message...>"}, {SCHEMA_VERSION: 1})


# noinspection DuplicatedCode
def test_init_grammar_ignores_a_full_file_path(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = tmp_path / GRAMMAR_IGNORED
    include = tmp_path / GRAMMAR_INCLUDE
    ignored.write_text("invalid", encoding="utf-8")
    include.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({str(ignored)}))

    result = router._grammar_init([ignored, include])

    assert result == ({"say": "<message...>"}, {SCHEMA_VERSION: 1})


# noinspection DuplicatedCode
def test_init_grammar_ignores_files_under_a_directory(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    ignored = ignored_dir / GRAMMAR_IGNORED
    include = tmp_path / GRAMMAR_INCLUDE
    ignored.write_text("invalid", encoding="utf-8")
    include.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({str(ignored_dir)}))

    result = router._grammar_init([ignored, include])

    assert result == ({"say": "<message...>"}, {SCHEMA_VERSION: 1})


def test_init_grammar_returns_validation_error(
    router: CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = tmp_path / GRAMMAR_INVALID
    invalid.write_text(_json_grammar().replace(f'"{SCHEMA_VERSION}": 1', f'"zz{SCHEMA_VERSION}": -1'), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset())

    result = router._grammar_init(invalid)

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
    monkeypatch.setattr(paths, "FIXTURES_HTTP", fixture_root / "http")

    def serve() -> None:
        try:
            # noinspection protected-member
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
    assert second._info == {SCHEMA_VERSION: 1}
