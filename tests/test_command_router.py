import http.client
import threading
from pathlib import Path

import pytest

import cmd_router as command_router_module

# noinspection protected-member
from cmd_router import REPL, CommandRouter, _CmdRouter
from cmd_router.lib.control import ControlType as Control
from cmd_router.utils.cli import flags
from cmd_router.utils.context import paths, uctx
from cmd_router.utils.status import Status, stat

CMD_ROUTER = uctx.CMD_ROUTER_SERIAL
SCHEMA_VERSION = uctx.SCHEMA_VERSION_SERIAL
GRAMMAR = uctx.GRAMMAR_SERIAL


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
def router() -> _CmdRouter:
    instance = _CmdRouter()
    instance.grammars = {}
    instance.info = {}
    return instance


def test_normalize_merges_grammar_and_info(router: _CmdRouter) -> None:
    router.normalize(*({"say": "<message...>"}, {SCHEMA_VERSION: 1}))

    assert router.grammars == {"say": "<message...>"}
    assert router.info == {SCHEMA_VERSION: 1}


def test_default_ignore_contains_one_filename() -> None:
    assert flags.ignore == frozenset({GRAMMAR_ERR})


def test_constructor_loads_non_lazy_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    grammar = tmp_path / GRAMMAR_JSON5
    grammar.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(paths, "FIXTURES", tmp_path)
    monkeypatch.setattr(flags, "lazy", False)
    monkeypatch.setattr(flags, "test_suite", False)

    private = _CmdRouter()
    private.grammars = {}
    private.info = {}
    monkeypatch.setattr(command_router_module, "_cmd_router", private)

    router = CommandRouter()

    assert router.initialize == stat.Success()
    assert router._grammars == {"say": "<message...>"}
    assert router._info == {SCHEMA_VERSION: 1}


def test_init_grammar_loads_supported_files_and_skips_unknown_files(
    router: _CmdRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_file = tmp_path / GRAMMAR_JSON5
    toml_file = tmp_path / GRAMMAR_TOML
    text_file = tmp_path / GRAMMAR_TXT
    json_file.write_text(_json_grammar("json"), encoding="utf-8")
    toml_file.write_text(_toml_grammar("toml"), encoding="utf-8")
    text_file.write_text("not a grammar", encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset())

    result = router.grammar_init([json_file, toml_file, text_file])

    assert result == (
        {"json": "<message...>", "toml": "<message...>"},
        {SCHEMA_VERSION: 1},
    )


def test_init_grammar_ignores_a_filename(router: _CmdRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ignored = tmp_path / GRAMMAR_IGNORED
    include = tmp_path / GRAMMAR_INCLUDE
    ignored.write_text("invalid", encoding="utf-8")
    include.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({ignored.name}))

    result = router.grammar_init([ignored, include])

    assert result == ({"say": "<message...>"}, {SCHEMA_VERSION: 1})


# noinspection DuplicatedCode
def test_init_grammar_ignores_a_full_file_path(
    router: _CmdRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored = tmp_path / GRAMMAR_IGNORED
    include = tmp_path / GRAMMAR_INCLUDE
    ignored.write_text("invalid", encoding="utf-8")
    include.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({str(ignored)}))

    result = router.grammar_init([ignored, include])

    assert result == ({"say": "<message...>"}, {SCHEMA_VERSION: 1})


# noinspection DuplicatedCode
def test_init_grammar_ignores_files_under_a_directory(
    router: _CmdRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    ignored = ignored_dir / GRAMMAR_IGNORED
    include = tmp_path / GRAMMAR_INCLUDE
    ignored.write_text("invalid", encoding="utf-8")
    include.write_text(_json_grammar(), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset({str(ignored_dir)}))

    result = router.grammar_init([ignored, include])

    assert result == ({"say": "<message...>"}, {SCHEMA_VERSION: 1})


def test_init_grammar_returns_validation_error(
    router: _CmdRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = tmp_path / GRAMMAR_INVALID
    invalid.write_text(_json_grammar().replace(f'"{SCHEMA_VERSION}": 1', f'"zz{SCHEMA_VERSION}": -1'), encoding="utf-8")
    monkeypatch.setattr(flags, "ignore", frozenset())

    result = router.grammar_init(invalid)

    assert isinstance(result, type(stat.Abort()))
    assert result.name == stat.Abort().name


def _post_to_lazy_router(
    monkeypatch: pytest.MonkeyPatch,
    router: _CmdRouter,
    payloads: list[bytes],
    fixture_root: Path,
) -> list[int]:
    ready = threading.Event()
    servers: list[command_router_module.HTTPServer] = []
    errors: list[BaseException] = []
    real_server = command_router_module.HTTPServer

    class _RecordingHTTPServer(real_server):
        def __init__(self, *args: object, **kwargs: object) -> None:
            # ty: ignore[invalid-argument-type]
            super().__init__(*args, **kwargs)
            servers.append(self)
            ready.set()

    # noinspection unresolved-references
    monkeypatch.setattr(command_router_module, "HTTPServer", _RecordingHTTPServer)
    monkeypatch.setattr(paths, "FIXTURES", fixture_root)
    monkeypatch.setattr(paths, "FIXTURES_HTTP", fixture_root / "http")

    def serve() -> None:
        try:
            # noinspection protected-member
            router.lazy_init()
        except BaseException as exception:  # pragma: no cover - surfaced by the assertion below
            errors.append(exception)

    thread = threading.Thread(target=serve)
    thread.start()
    assert ready.wait(timeout=2), errors
    server = servers[0]
    statuses: list[int] = []
    for payload in payloads:
        # ty: ignore[invalid-argument-type, parameter-already-assigned]
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

    first = _CmdRouter.__new__(_CmdRouter)
    first.grammars = {}
    first.info = {}

    second = _CmdRouter.__new__(_CmdRouter)
    second.grammars = {}
    second.info = {}

    assert _post_to_lazy_router(monkeypatch, first, [payload], tmp_path) == [204]
    assert _post_to_lazy_router(monkeypatch, second, [payload], tmp_path) == [204]
    assert len(list((tmp_path / "http").glob(f"grammar-*{extension}"))) == 1
    assert second.grammars == {"say": "<message...>"}
    assert second.info == {SCHEMA_VERSION: 1}


def _initialized_control_router() -> CommandRouter:
    router = CommandRouter.__new__(CommandRouter)
    router.control = Control()
    assert router.control.initialize({"say": "<message...>"}).ok
    return router


def test_handle_command_known_returns_none() -> None:
    router = _initialized_control_router()
    try:
        assert router._handle_command("/say hello") is None
        assert router.control.deeper_context.last_result is not None
        assert router.control.deeper_context.last_result.command == "say"
    finally:
        router.control.close()


def test_handle_command_unknown_returns_suggestions() -> None:
    router = _initialized_control_router()
    try:
        outcome = router._handle_command("/unknown")
        assert isinstance(outcome, list)
    finally:
        router.control.close()


@pytest.mark.parametrize("marker", ["exit", "e", "quit", "q", "!q", "!Quit", "  QUIT  "])
def test_handle_command_quit_markers_exit(marker: str) -> None:
    router = _initialized_control_router()
    try:
        assert router._handle_command(marker) == stat.Success()
    finally:
        router.control.close()


@pytest.mark.parametrize("empty", ["", "   "])
def test_handle_command_empty_keeps_listening(empty: str) -> None:
    router = _initialized_control_router()
    try:
        assert router._handle_command(empty) is None
    finally:
        router.control.close()


def test_handle_command_converts_execution_exception_to_abort() -> None:
    router = _initialized_control_router()

    def fail(_command: str) -> None:
        raise RuntimeError("broken control")

    # noinspection unresolved-references
    router.control.execute = fail  # type: ignore[method-assign]

    try:
        assert router._handle_command("/say hello") == stat.Abort()
    finally:
        router.control.close()


def test_handle_command_converts_invalid_result_to_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _initialized_control_router()
    monkeypatch.setattr(router.control, "execute", lambda _command: "not-a-result")  # type: ignore[method-assign]
    try:
        assert router._handle_command("/say hello") == stat.Abort()
    finally:
        router.control.close()


def test_handle_command_non_string_returns_tokenize_error() -> None:
    router = _initialized_control_router()
    try:
        assert router._handle_command(None) == stat.TokenizeUnsupportedTypeError()  # ty: ignore[invalid-argument-type]
    finally:
        router.control.close()


def test_suite_loop_returns_repl_status(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _initialized_control_router()

    class _FakeApp:
        def run(self) -> Status:
            return stat.Success()

    monkeypatch.setattr(command_router_module, "REPL", lambda handle: _FakeApp())
    try:
        assert router._test_suite_loop() == stat.Success()
    finally:
        router.control.close()


def test_suite_loop_refuses_uninitialized_control() -> None:
    router = CommandRouter.__new__(CommandRouter)
    router.control = Control()
    try:
        assert router._test_suite_loop() == stat.ControlNotInitializedError()
    finally:
        router.control.close()


def test_suite_loop_converts_repl_crash_to_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _initialized_control_router()

    class _CrashingApp:
        def run(self) -> Status:
            raise RuntimeError("repl blew up")

    monkeypatch.setattr(command_router_module, "REPL", lambda handle: _CrashingApp())
    try:
        assert router._test_suite_loop() == stat.Abort()
    finally:
        router.control.close()


def test_suite_loop_converts_none_exit_to_impossible(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _initialized_control_router()

    class _NoneApp:
        def run(self) -> None:
            return None

    monkeypatch.setattr(command_router_module, "REPL", lambda handle: _NoneApp())
    try:
        assert router._test_suite_loop() == stat.ImpossibleControlState()
    finally:
        router.control.close()


def test_repl_compose_yields_input_and_two_statics() -> None:
    from textual.widgets import Input, Static

    app = REPL(handle=lambda _command: None)
    widgets = list(app.compose())
    assert isinstance(widgets[0], Input)
    assert isinstance(widgets[1], Static)
    assert isinstance(widgets[2], Static)


def test_repl_local_tab_suggestions_follow_the_current_command(monkeypatch: pytest.MonkeyPatch) -> None:
    control = Control()
    assert control.initialize({"gamemode": "(survival|creative|adventure|spectator)"}).ok
    monkeypatch.setattr(flags, "suggestions_server", False)
    monkeypatch.setattr(flags, "no_suggestions_server", False)
    try:
        app = REPL(handle=lambda _command: None, context=control.deeper_context)

        assert app._suggestions_for_input("/ga") == ["gamemode"]
        assert app._suggestions_for_input("/gamemode ") == ["survival"]
        assert app._suggestions_for_input("/gamemode survival") == []
        assert app._completion_start("/ga", "/") == 1
        assert app._matching_suggestions(["gamemode"], "") == ["gamemode"]
    finally:
        control.close()


def test_repl_uses_server_suggestions_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def compute(command_text: str) -> tuple[list[str], None]:
        calls.append(command_text)
        return ["gamemode", "give"], None

    monkeypatch.setattr(flags, "suggestions_server", True)
    monkeypatch.setattr(flags, "no_suggestions_server", False)
    monkeypatch.setattr(command_router_module.LazySuggestionsServer, "_compute_suggestions", staticmethod(compute))

    app = REPL(handle=lambda _command: None)

    assert app._suggestions_for_input("/ga") == ["gamemode", "give"]
    assert calls == ["/ga"]


def test_repl_does_not_replace_a_completed_literal_with_child_suggestions() -> None:
    control = Control()
    assert control.initialize({"advancement": "(grant|revoke) <target>"}).ok
    try:
        app = REPL(handle=lambda _command: None, context=control.deeper_context)

        assert app._suggestions_for_input("/advancement") == ["grant"]
        assert app._matching_suggestions(["grant", "revoke"], "/advancement") == []
        assert app._matching_suggestions(["grant", "revoke"], "/advancement ") == ["grant", "revoke"]
    finally:
        control.close()
