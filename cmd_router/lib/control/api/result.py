#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Structured results returned by control initialization and execution.

The control API reports expected failures as values rather than requiring
callers to catch parser, grammar, or action exceptions.  ``ControlResult``
describes one command attempt and may represent ordinary non-command input,
successful dispatch, tokenization/grammar mismatch, or an action failure.
Successful parses retain the dispatcher ``ParseResult``, command context, and
handler so integrations can inspect exactly what ran.  Parse failures retain
the structured ``ParseError`` with its furthest token position and
expectations.

``ControlInitialization`` describes fixture loading and grammar compilation.
Its ``exception`` field is a formatted diagnostic string, not the live
exception object; this keeps results serializable while preserving useful
failure context.  Both result types are immutable dataclasses, are truthy only
when ``ok`` is true, and expose ``to_dict``/``as_dict`` for transport layers.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cmd_router.lib.command import CmdParse

__all__ = ("ControlResult", "ControlInitialization")

_Action = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ControlResult:
    """Describe one command attempt and preserve its parse/execution details.

    ``kind`` distinguishes the control-layer stage that produced the result.
    For a successful command, ``context`` contains parsed and override-applied
    arguments while ``parse_result`` contains the original parser result.  For
    a parse failure, ``error`` contains the structured furthest failure.  For
    an action failure, ``exception`` contains a printable exception summary
    and ``handler`` identifies the handler that was selected.
    """

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
    """Describe fixture setup and grammar-compilation status.

    ``command_count`` is populated on successful grammar compilation.  Fixture
    failures use the centralized ``ControlFixtureError`` code, while malformed
    setup or grammar values use the corresponding control initialization code.
    The object is intentionally small so it can be returned directly from the
    module-level API and serialized with ``to_dict``.
    """

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
