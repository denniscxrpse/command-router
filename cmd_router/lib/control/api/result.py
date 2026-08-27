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

__all__ = ("ControlResult", "ControlInitialization")

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cmd_router.lib.command import CmdParse
from cmd_router.utils.cli import *
from cmd_router.utils.logger import *

_Action = Callable[..., Any]


class _UNSET: ...


@dataclass(frozen=True, slots=True)
class ControlResult:
    """Describe one command attempt and preserve its parse/execution details.

    ``kind`` distinguishes the control-layer stage that produced the result.
    For a successful command, ``context`` contains parsed and override-applied
    arguments, while ``parse_result`` contains the original parser result.  For
    a parse failure, ``error`` contains the structured furthest failure.  For
    an action failure, ``exception`` contains a printable exception summary
    and ``handler`` identifies the handler that was selected.

    - ok: Whether the control operation succeeded. Used as the boolean value of the result instance.
    - code: Centralized status or error code for the operation.
    - kind: Stage that produced the result, such as ``command`` or ``parse_error``.
    - input: Exact value supplied by the caller before parsing or prefix handling.
    - command: Matched command name, without the command prefix. ``None`` if no command was matched.
    - value: Value returned by the action handler, or pass-through input value for non-command input.
      Defaults to ``None``.
    - parse_result: Original parser result before control overrides are applied. ``None`` for
      non-command input or parse failures.
    - context: Parsed context including final controlled arguments after overrides. ``None`` for
      parse failures or non-command input.
    - handler: Handler function selected for the matched command. ``None`` if no command was
      matched or parse failed.
    - error: Structured parser error for a failed parse, containing the furthest token position
      and expectations. ``None`` for successful parses.
    - message: Human-readable explanation of the result. Empty string by default.
    - exception: Formatted exception details (as string) from a failed action. ``None`` if the
      action succeeded or no action was attempted.
    - data: Primary response data for transport layers. Defaults to ``value`` if not explicitly
      provided.
    - error_payload: Response error payload for transport layers. Defaults to ``error``, then
      ``exception``, then ``message`` (if not ok), otherwise ``None``. Arbitrary caller-provided
      values are preserved.
    """

    def __bool__(self) -> bool:
        """Use the result status as its boolean value."""
        return self.ok

    ok: bool
    """Whether the control operation succeeded."""
    code: int
    """Centralized status or error code for the operation."""
    kind: str
    """Stage that produced the result, such as "command" or "parse_error"."""
    input: Any
    """Exact value supplied by the caller, before parsing or prefix handling."""
    command: str | None = None
    """Matched command name, without the command prefix."""
    value: Any = None
    """Value returned by the action, or pass-through input value."""
    parse_result: CmdParse.Result | None = None
    """Original parser result before control overrides."""
    context: CmdParse.Context | None = None
    """Parsed context, including final controlled arguments."""
    handler: _Action | None = None
    """Handler selected for the matched command."""
    error: CmdParse.Error | None = None
    """Structured parser error for a failed parse."""
    message: str = ""
    """Human-readable explanation of the result."""
    exception: str | None = None
    """Formatted exception details from a failed action."""
    data: Any = _UNSET
    """Primary response data, defaulting to the legacy ``value`` field."""
    error_payload: Any = _UNSET
    """Response error payload; arbitrary caller-provided values are preserved. Do not confuse with ``error``."""

    def __set_attr__(self, name: str, value: Any) -> None:
        """Set one declared slot bypassing ``frozen`` for initialization."""

        # ``frozen`` + ``slots`` still allows writes through
        # ``object.__setattr__``, but only for names declared as fields;
        # anything else fails because the instance has no such slot.

        # DO NOT pass ``__name__`` if the stored attribute is ``_UNSET``;
        # IT WILL NOT WORK.

        try:
            object.__setattr__(self, name, value)
        except AttributeError:
            log.critical(f"logic error? __set_attr__ failed. does '{name}' even exist at self?")
            raise RuntimeError("post initialization of results failed!") from None

    def __post_init__(self) -> None:
        """Fill the response aliases without changing existing constructors."""
        if self.data is _UNSET:
            self.__set_attr__("data", self.value)
        if self.error_payload is _UNSET:
            response_error: Any = self.error
            if response_error is None:
                response_error = self.exception
            if response_error is None and not self.ok:
                response_error = self.message or None
            self.__set_attr__("error_payload", response_error)

    @property
    def is_success(self) -> bool:
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
        return self.data

    @property
    def suggestions(self) -> list[str]:
        if flags.no_suggestions:
            # TODO: implement suggestions logic
            ...
        return []

    def to_response(self) -> dict[str, Any]:
        """Return the compact ``data``/``err`` response written to stderr."""
        return self._all_data(response_only=True)

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-friendly result mapping."""
        data = self._all_data()
        if self.context is not None:
            data["parsed_args"] = dict(self.context.args)
        if self.error is not None:
            data["error"] = self.error.to_dict()
        if self.message:
            data["message"] = self.message
        if self.exception is not None:
            data["exception"] = self.exception
        return data

    def to_json(self, is_response: bool = False):
        """Serialize the result to JSON.

        Args:
            is_response: If True, returns a compact JSON response containing only
                ``data``, ``err``, and ``suggestions`` fields suitable for client
                consumption. If False (default), returns the full result dictionary
                with all diagnostic fields including ``ok``, ``code``, ``kind``,
                ``parsed_args``, ``error``, ``message``, and ``exception``.

        Returns:
            A JSON string representing either the compact response format or the
            complete result structure.
        """
        return json.dumps(self.to_response() if is_response else self.to_dict())

    as_response = to_response
    as_dict = to_dict
    as_json = to_json

    @staticmethod
    def _transport_value(value: Any) -> Any:
        """Convert known structured errors while preserving arbitrary payloads."""
        if isinstance(value, CmdParse.Error):
            return value.to_dict()
        return value

    def _all_data(self, response_only: bool = False) -> dict[str, Any]:
        if response_only:
            return {
                "data": self.data,
                "err": self._transport_value(self.error_payload),
                "suggestions": self.suggestions,
            }
        return {
            "ok": self.ok,
            "code": self.code,
            "kind": self.kind,
            "input": self.input,
            "command": self.command,
            "value": self.value,
            "data": self.data,
            "err": self._transport_value(self.error_payload),
            "suggestions": self.suggestions,
        }


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
