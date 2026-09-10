#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

#  The Clear BSD License
#
"""Edge cases the main suites do not cover: hostile input must not escape.

Every test here pins the library's core contract: expected failures are
returned as values (``ControlResult``/``ControlInitialization``/``Status``),
never raised, even for hostile or malformed input.
"""

import http.client
import json
import threading
from collections.abc import Mapping
from http.server import HTTPServer

import pytest
from click.testing import CliRunner

from cmd_router.lib.commands import CmdNode
from cmd_router.lib.commands.typing import ArgumentType
from cmd_router.lib.control import ControlType as Control
from cmd_router.suggestions import LazySuggestionsServer, lazy_suggest_srv_ctx
from cmd_router.utils.cli import flags, init_flags
from cmd_router.utils.status import stat


@pytest.fixture
def _clean_flags(monkeypatch: pytest.MonkeyPatch):
    """Isolate process-wide flags mutated by edge probes."""
    monkeypatch.setattr(flags, "json_out", False)
    monkeypatch.setattr(flags, "no_suggestions", False)
    monkeypatch.setattr(flags, "max_sized_suggestions", False)
    yield


def test_huge_int_returns_invalid_argument_instead_of_raising(_clean_flags) -> None:
    runner = Control()
    try:
        assert runner.initialize({"tp": "<x:int> <y:int> <z:int>"}).ok
        result = runner.execute(f"/tp {'9' * 5000} 1 2")
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == "INVALID_ARGUMENT"
    finally:
        runner.close()


def test_raising_argument_type_returns_invalid_argument_instead_of_raising(_clean_flags) -> None:
    class _Exploding(ArgumentType[str]):
        def parse(self, value: str) -> str:
            raise RuntimeError("boom")

    root = CmdNode.Root()
    literal = CmdNode.Literal("go")
    root.add_child(literal)
    literal.add_child(CmdNode.Argument("target", _Exploding()))

    dispatcher = CmdNode.Dispatcher(root)
    parsed = dispatcher.parse("go now")
    assert not parsed.ok
    assert parsed.error is not None
    assert parsed.error.kind == "UNEXPECTED_COMMAND" or parsed.error.kind == "INVALID_ARGUMENT"


def test_bytes_input_with_json_out_returns_result_instead_of_raising(_clean_flags, monkeypatch) -> None:
    monkeypatch.setattr(flags, "json_out", True)
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}).ok
        result = runner.execute(b"hi")
        assert not result.ok
    finally:
        runner.close()


def test_non_serializable_action_value_with_json_out_returns_result(_clean_flags, monkeypatch) -> None:
    monkeypatch.setattr(flags, "json_out", True)
    runner = Control()
    try:
        runner.deeper_context.command_action = {"say": lambda **arguments: object()}
        assert runner.initialize({"say": "<message...>"}).ok
        result = runner.execute("/say hi")
        assert result.ok
    finally:
        runner.close()


def test_unreadable_grammar_mapping_returns_init_error(_clean_flags) -> None:
    class _Boom(Mapping):
        def __getitem__(self, key):
            raise RuntimeError("boom")

        def __iter__(self):
            raise RuntimeError("boom")

        def __len__(self):
            return 1

    runner = Control()
    try:
        result = runner.initialize(_Boom())
        assert not result.ok
    finally:
        runner.close()


def test_deeply_nested_grammar_returns_init_error(_clean_flags) -> None:
    runner = Control()
    try:
        result = runner.initialize({"cmd": "[" * 3000 + "<x>" + "]" * 3000})
        assert not result.ok
    finally:
        runner.close()


def test_no_suggestions_server_flag_disables_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "no_suggestions_server", False)
    result = CliRunner().invoke(init_flags, ["--no-suggestions-server"])
    assert result.exit_code == 0
    assert flags.no_suggestions_server is True


def test_unicode_digits_rejected_as_invalid_argument(_clean_flags) -> None:
    runner = Control()
    try:
        assert runner.initialize({"tp": "<x:int>"}).ok
        result = runner.execute("/tp \u0661\u0662\u0663")
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == "INVALID_ARGUMENT"
    finally:
        runner.close()


def test_sign_only_rejected_as_invalid_argument(_clean_flags) -> None:
    runner = Control()
    try:
        assert runner.initialize({"tp": "<x:int>"}).ok
        for bad in ("+", "-"):
            result = runner.execute(f"/tp {bad}")
            assert not result.ok
    finally:
        runner.close()


def test_unterminated_quote_returns_tokenization_error(_clean_flags) -> None:
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}).ok
        result = runner.execute('/say "hello')
        assert not result.ok
        assert result.error is not None
        assert result.error.kind == "TOKENIZATION"
    finally:
        runner.close()


def test_prefix_only_returns_invalid_input(_clean_flags) -> None:
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}).ok
        result = runner.execute("/")
        assert not result.ok
        assert result.code.name == stat.Abort().name
    finally:
        runner.close()


def test_empty_greedy_argument_succeeds(_clean_flags) -> None:
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}).ok
        result = runner.execute('/say ""')
        assert result.ok
        assert result.parsed_args == {"message": ""}
    finally:
        runner.close()


def test_set_suggestions_rejects_non_strings() -> None:
    with pytest.raises(TypeError):
        lazy_suggest_srv_ctx.set_suggestions([object()])  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError):
        lazy_suggest_srv_ctx.set_suggestions("not-a-list")  # ty: ignore[invalid-argument-type]


@pytest.fixture
def _live_server(monkeypatch: pytest.MonkeyPatch):
    """Serve the suggestions server with an initialized control surface."""
    from cmd_router.lib.control.api.control import control as shared

    monkeypatch.setattr(flags, "suggestions_server", True)
    monkeypatch.setattr(flags, "no_suggestions_server", False)
    lazy_suggest_srv_ctx.clear()
    deeper = shared.deeper_context
    saved = (deeper.initialized, deeper.grammars, deeper.dispatcher)
    assert shared.initialize({"say": "<message...>"}).ok
    server = HTTPServer(("127.0.0.1", 0), LazySuggestionsServer)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    shared.close()
    deeper.initialized, deeper.grammars, deeper.dispatcher = saved
    lazy_suggest_srv_ctx.clear()


def _raw_request(server: HTTPServer, method: str):
    # ty: ignore[invalid-argument-type, parameter-already-assigned]
    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
    try:
        connection.request(method, "/")
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "OPTIONS"])
def test_unsupported_methods_return_json_501(_live_server: HTTPServer, method: str) -> None:
    status, content_type, body = _raw_request(_live_server, method)
    assert status == 501
    assert content_type == "application/json"
    assert json.loads(body)["message"] == f"unsupported method: {method}"


def test_head_returns_501_without_body(_live_server: HTTPServer) -> None:
    status, _, body = _raw_request(_live_server, "HEAD")
    assert status == 501
    assert body == b""
