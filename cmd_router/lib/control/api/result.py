#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Result objects exposed by the control API."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cmd_router.lib.command import CmdParse

_Action = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ControlResult:
    """Describe one command-control result."""

    ok: bool
    code: int
    kind: str
    input: Any
    command: str | None = None
    value: Any = None
    parse_result: CmdParse.Result | None = None
    context: CmdParse.Context | None = None
    handler: _Action | None = None
    error: CmdParse.Error | None = None
    message: str = ""
    exception: str | None = None

    @property
    def success(self) -> bool:
        """Return whether the operation succeeded."""
        return self.ok

    @property
    def parsed_args(self) -> dict[str, Any]:
        """Return the controlled arguments."""
        if self.context is None:
            return {}
        return dict(self.context.args)

    @property
    def result(self) -> Any:
        """Return the action result value."""
        return self.value

    def __bool__(self) -> bool:
        """Use the result status as its boolean value."""
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly result mapping."""
        data: dict[str, Any] = {
            "ok": self.ok,
            "code": self.code,
            "kind": self.kind,
            "input": self.input,
            "command": self.command,
            "value": self.value,
        }
        if self.context is not None:
            data["parsed_args"] = dict(self.context.args)
        if self.error is not None:
            data["error"] = {
                "kind": self.error.kind,
                "token_index": self.error.token_index,
                "expected": self.error.expected,
                "message": self.error.message,
                "partial_args": dict(self.error.partial_args),
                "code": None if self.error.code is None else self.error.code,
            }
        if self.message:
            data["message"] = self.message
        if self.exception is not None:
            data["exception"] = self.exception
        return data

    as_dict = to_dict


@dataclass(frozen=True, slots=True)
class ControlInitialization:
    """Describe the result of control initialization."""

    ok: bool
    code: int
    message: str = ""
    command_count: int = 0
    exception: str | None = None

    def __bool__(self) -> bool:
        """Use the initialization status as its boolean value."""
        return self.ok

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly initialization mapping."""
        data: dict[str, Any] = {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "command_count": self.command_count,
        }
        if self.exception is not None:
            data["exception"] = self.exception
        return data

    as_dict = to_dict
