#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

import pytest

import main as entrypoint
from cmd_router.lib.commands import CmdError
from cmd_router.lib.commands.typing import ArgumentParseError

# noinspection protected-member
from cmd_router.lib.control.compiler import _compile_grammars
from cmd_router.utils.logger import log
from cmd_router.utils.status import stat


def _emit_callsite_log() -> None:
    log.info("logger callsite")


def test_status_namespace_exposes_expected_members() -> None:
    assert hasattr(stat, "Abort")
    assert hasattr(stat, "Success")
    assert hasattr(stat, "Interrupted")
    assert not hasattr(stat, "exit_code")
    assert not hasattr(stat, "FatalError")
    assert not hasattr(stat, "FatalOSError")


def test_cmd_error_aliases_status_with_argument_error() -> None:
    assert issubclass(type(stat.Abort()), CmdError)
    assert stat.ArgumentParseError is ArgumentParseError
    assert stat.ArgumentParseError.__name__ == "ArgumentParseError"


def test_main_logs_exception_message_and_returns_abort_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoint, "init_flags", lambda **_kwargs: None)

    def fail() -> None:
        raise ValueError("bad value")

    monkeypatch.setattr(entrypoint, "CommandRouter", fail)
    messages: list[object] = []
    monkeypatch.setattr(entrypoint.log, "critical", lambda *message: messages.extend(message))

    assert entrypoint.main().code == stat.Abort().code
    assert messages == ["bad value"]


def test_diagnostic_logs_are_formatted_on_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    log.info("logger smoke test: %s", "stdout")

    captured = capsys.readouterr()
    assert "logger smoke test: stdout" in captured.out
    assert captured.err == ""


def test_diagnostic_logs_include_callsite(capsys: pytest.CaptureFixture[str]) -> None:
    _emit_callsite_log()

    captured = capsys.readouterr()
    assert f"{__name__}._emit_callsite_log: logger callsite" in captured.out


def test_diagnostic_logs_skip_project_package_prefix(capsys: pytest.CaptureFixture[str]) -> None:
    _compile_grammars({}, lambda: {}, False, "/")

    captured = capsys.readouterr()
    assert "lib.control.compiler._compile_grammars: starting compilation of 0 grammar entries" in captured.out
