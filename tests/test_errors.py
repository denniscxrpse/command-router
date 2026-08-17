#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

import pytest

import main as entrypoint
from cmd_router.lib.command import CmdError
from cmd_router.lib.command.typing import ArgumentParseError
from cmd_router.utils.context import error


def test_error_codes_do_not_classify_exceptions() -> None:
    assert not hasattr(error, "exit_code")
    assert not hasattr(error, "FatalError")
    assert not hasattr(error, "FatalOSError")


def test_cmd_error_exposes_codes_and_argument_errors() -> None:
    assert CmdError is error
    assert CmdError.ArgumentParseError is ArgumentParseError
    assert CmdError.ArgumentParseError.__name__ == "ArgumentParseError"


def test_main_logs_exception_message_and_returns_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoint, "init_flags", lambda **_kwargs: None)

    def fail() -> None:
        raise ValueError("bad value")

    monkeypatch.setattr(entrypoint, "CommandRouter", fail)
    messages: list[object] = []
    monkeypatch.setattr(entrypoint.log, "critical", lambda *message: messages.extend(message))

    assert entrypoint.main() == error.Abort
    assert messages == ["bad value"]
