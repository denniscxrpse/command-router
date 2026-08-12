#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

import pytest

import main as entrypoint
from cmd_router.lib.command import CmdError
from cmd_router.utils.context import error


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (Exception(), error.FatalError),
        (MemoryError(), error.FatalMemoryError),
        (ImportError(), error.FatalImportError),
        (OSError(), error.FatalOSError),
        (TypeError(), error.FatalTypeError),
        (ValueError(), error.FatalValueError),
        (RuntimeError(), error.FatalRuntimeError),
        (KeyboardInterrupt(), error.Interrupted),
    ],
)
def test_fatal_exceptions_have_stable_exit_codes(exception: BaseException, expected: int) -> None:
    assert error.exit_code(exception) == int(expected)


def test_cmd_error_is_the_central_error_code_namespace() -> None:
    assert CmdError is error
    assert CmdError.ArgumentParseError.__name__ == "ArgumentParseError"


def test_main_returns_the_fatal_exception_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entrypoint, "init_flags", lambda **_kwargs: None)

    def fail() -> None:
        raise ValueError("bad value")

    monkeypatch.setattr(entrypoint, "CommandRouter", fail)
    monkeypatch.setattr(entrypoint.log, "critical", lambda *_message: None)

    assert entrypoint.main() == error.FatalValueError
