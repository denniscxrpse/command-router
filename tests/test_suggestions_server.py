#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

#  The Clear BSD License
#
"""HTTP behavior of ``LazySuggestionsServer`` (POST stores, GET serves JSON)."""

import http.client
import json
import threading
from http.server import HTTPServer

import pytest

from cmd_router.lib.control.api.control import control as _shared_control
from cmd_router.suggestions import LazySuggestionsServer, lazy_suggest_srv_ctx
from cmd_router.suggestions.algo import fuzzy_str_match
from cmd_router.utils.cli import flags
from cmd_router.utils.status import stat

_GRAMMARS = {
    "gamemode": "(survival|creative)",
    "say": "<message...>",
    "tell": "<target> <message...>",
}


@pytest.fixture
def _enabled_server(monkeypatch: pytest.MonkeyPatch):
    """Serve ``LazySuggestionsServer`` on an ephemeral port with control ready."""
    monkeypatch.setattr(flags, "suggestions_server", True)
    monkeypatch.setattr(flags, "no_suggestions_server", False)
    lazy_suggest_srv_ctx.clear()

    deeper = _shared_control.deeper_context
    saved = (deeper.initialized, deeper.grammars, deeper.dispatcher)
    assert _shared_control.initialize(dict(_GRAMMARS)).ok

    server = HTTPServer(("127.0.0.1", 0), LazySuggestionsServer)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
    )
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
    _shared_control.close()
    deeper.initialized, deeper.grammars, deeper.dispatcher = saved
    lazy_suggest_srv_ctx.clear()


def _request(server: HTTPServer, method: str, path: str = "/", body: bytes | None = None):
    # ty: ignore[invalid-argument-type, parameter-already-assigned]
    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
    try:
        connection.request(method, path, body=body)
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        connection.close()


def test_get_before_post_returns_empty_json_list(_enabled_server: HTTPServer) -> None:
    status, content_type, body = _request(_enabled_server, "GET")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == []


def test_post_then_get_round_trip(_enabled_server: HTTPServer) -> None:
    status, _, _ = _request(_enabled_server, "POST", body=b"gamemode")
    assert status == 204

    status, content_type, body = _request(_enabled_server, "GET")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == ["survival", "creative"]


def test_post_path_fallback_when_body_empty(_enabled_server: HTTPServer) -> None:
    status, _, _ = _request(_enabled_server, "POST", path="/gamemod", body=b"")
    assert status == 204

    status, _, body = _request(_enabled_server, "GET")
    assert status == 200
    assert json.loads(body) == ["gamemode"]


def test_post_complete_command_stores_empty(_enabled_server: HTTPServer) -> None:
    status, _, _ = _request(_enabled_server, "POST", body=b"say hello")
    assert status == 204

    status, _, body = _request(_enabled_server, "GET")
    assert status == 200
    assert json.loads(body) == []


def test_disabled_post_ignored_and_get_empty(_enabled_server: HTTPServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "suggestions_server", False)

    status, _, _ = _request(_enabled_server, "POST", body=b"gamemode")
    assert status == 204
    assert lazy_suggest_srv_ctx.get_suggestions() == []

    status, _, body = _request(_enabled_server, "GET")
    assert status == 200
    assert json.loads(body) == []


def test_no_suggestions_server_flag_disables(_enabled_server: HTTPServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "no_suggestions_server", True)

    status, _, _ = _request(_enabled_server, "POST", body=b"gamemode")
    assert status == 204

    status, _, body = _request(_enabled_server, "GET")
    assert status == 200
    assert json.loads(body) == []


def test_invalid_utf8_body_returns_400(_enabled_server: HTTPServer) -> None:
    status, _, _ = _request(_enabled_server, "POST", body=b"\xff\xfe")
    assert status == 400


def test_uninitialized_control_returns_503(_enabled_server: HTTPServer) -> None:
    deeper = _shared_control.deeper_context
    deeper.initialized = False
    try:
        status, _, _ = _request(_enabled_server, "POST", body=b"gamemode")
        assert status == 503
    finally:
        deeper.initialized = True


def test_disabled_status_contract_and_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    assert LazySuggestionsServer._err("POST").name == stat.SuggestionServerDisabled().name

    monkeypatch.setattr(flags, "suggestions_server", False)
    monkeypatch.setattr(flags, "no_suggestions_server", False)
    assert LazySuggestionsServer._disabled() is True

    monkeypatch.setattr(flags, "suggestions_server", True)
    assert LazySuggestionsServer._disabled() is False

    monkeypatch.setattr(flags, "no_suggestions_server", True)
    assert LazySuggestionsServer._disabled() is True


def test_fuzzy_match_limit_edge_returns_empty() -> None:
    assert fuzzy_str_match(None, ["a", "b"], 0) == []
    assert fuzzy_str_match(None, ["a", "b"], -1) == []
    assert fuzzy_str_match("a", ["a"], -3) == []
