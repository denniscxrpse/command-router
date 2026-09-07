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

__all__ = ("ControlResultKinds", "ControlResult", "ControlInitialization")

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Self, final

from cmd_router.utils.cli import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import *

_Action = Callable[..., Any]

if TYPE_CHECKING:
    from cmd_router.lib.commands import CmdParse


class _UNSET: ...


@final
class ControlResultKinds(StrEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values) -> str:
        # By default, StrEnum returns name.lower() here.
        # We override it to return the name as-is, which is already uppercase
        # since Python enum member names are conventionally uppercase.
        return name

    INPUT = auto()
    COMMAND = auto()
    TOKENIZATION = auto()

    NOT_INITIALIZED = auto()

    PARSE_ERROR = auto()
    ACTION_ERROR = auto()

    INVALID_INPUT = auto()
    INVALID_CONTEXT = auto()
    INVALID_ARGUMENT = auto()

    UNEXPECTED_TOKEN = auto()
    UNEXPECTED_COMMAND = auto()

    # noinspection bad-return
    @property
    def custom(self) -> Self:
        """Return the custom kind configured for this result kind."""
        custom = getattr(self, "_custom_kind", None)
        return self if custom is None else custom

    # noinspection unresolved-references
    @custom.setter
    def custom(self, kind: str) -> None:
        """Configure a custom kind while keeping it a valid enum instance."""
        if not isinstance(kind, str):
            raise TypeError(f"custom kind must be a str, got {type(kind).__name__}")

        # noinspection string-conversion-without-dunder-method
        custom = str.__new__(type(self), kind)
        custom._name_ = kind.upper()
        custom._value_ = kind
        object.__setattr__(self, "_custom_kind", custom)


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
      ``exception``, then ``message`` (if not ok), otherwise ``None``. Stored as-is, but
      ``to_response`` always transports it as ``dict|null`` via ``_transport_value``.
    """

    def __bool__(self) -> bool:
        """Use the result status as its boolean value."""
        return self.ok

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
        if self.error_payload is _UNSET:
            response_error: Any = self.error
            if response_error is None:
                response_error = self.exception
            if response_error is None and not self.ok:
                response_error = self.message or None
            self.__set_attr__("error_payload", response_error)

    ok: bool
    """Whether the control operation succeeded."""
    code: Status
    """Centralized status or error code for the operation."""
    kind: ControlResultKinds
    """Stage that produced the result, such as "command" or "parse_error"."""
    input: Any
    """Exact value supplied by the caller, before parsing or prefix handling."""
    command: str | None = None
    """Matched command name, without the command prefix."""
    value: Any = _UNSET
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
    error_payload: Any = _UNSET
    """Response error payload; stored as-is but transported as ``dict|null``. Do not confuse with ``error``."""

    @property
    def data(self) -> Any:
        """Return the primary response data."""
        return self.value if self.value is not _UNSET else self.error_payload

    @property
    def is_success(self) -> bool:
        """Return whether the operation succeeded."""
        return self.ok

    @property
    def parsed_args(self) -> dict[str, Any]:
        """Return the controlled arguments."""
        if self.context is None:
            log.warning("parsed_args requested on non-command input? no context was provided.")
            return {}
        return dict(self.context.args)

    @property
    def result(self) -> Any:
        """Return the action result value."""
        return self.value

    @property
    def suggestions(self) -> list[str] | None:
        """Return top-level completion hints mirroring the parse error.

        ``None`` when ``flags.no_suggestions`` disables hints. When a
        ``ParseError`` is present, this delegates to its ``_get_suggestions``
        (prefix-narrowed then Levenshtein-ranked ``expected`` with limit ``N``
        from ``FixturesSetup.suggestions_set_current_size``); otherwise ``[]``.
        """
        if flags.no_suggestions:
            return None
        if self.error is not None:
            return self.error._get_suggestions()
        return []

    def to_response(self) -> dict[str, Any]:
        """Return the compact contract mapping written to stderr.

        Always contains exactly ``ok``, ``input``, ``value``,
        ``suggestions``, ``error``, and ``message``. ``suggestions`` mirrors
        ``error["suggestions"]`` when a parse error exists (``None`` when
        disabled, else ``[]``). ``error`` is always ``dict|null`` via
        ``_transport_value``. Missing values are ``None`` rather than omitted,
        so consumers can rely on a fixed shape for both dicts and JSON.
        """
        return self._all_data(response_only=True)

    def to_dict(self) -> dict[str, Any]:
        """Return the full contract mapping.

        Always contains exactly ``ok``, ``code``, ``kind``, ``input``,
        ``command``, ``value``, ``parsed_args``, ``error``, ``message``, and
        ``exception``. ``error`` is ``dict|null`` (``ParseError.to_dict()``
        with its ``suggestions`` list). Missing values are ``None`` rather
        than omitted so consumers can rely on a fixed shape for both plain
        dictionaries and JSON.
        """
        return self._all_data()

    def to_json(self, is_response: bool = False):
        """Serialize the result to JSON.

        Args:
            is_response: If True, returns the compact contract JSON containing
                ``ok``, ``input``, ``value``, ``suggestions``, ``error``, and
                ``message``. If False (default), returns the full contract JSON
                with all diagnostic fields including ``code``, ``kind``,
                ``command``, ``parsed_args``, and ``exception``.

        Returns:
            A JSON string representing either the compact response format or the
            complete result structure. Both shapes keep every contract key and
            use ``null`` for absent values.
        """
        return json.dumps(self.to_response() if is_response else self.to_dict())

    as_response = to_response
    as_dict = to_dict
    as_json = to_json

    @staticmethod
    def _transport_value(value: Any) -> dict[str, Any] | None:
        """Transport ``error_payload`` as ``dict|null`` for the compact contract.

        - ``None``/``_UNSET`` becomes ``None``.
        - ``ParseError`` becomes its ``to_dict()`` (which carries ``suggestions``).
        - ``dict`` is returned as-is (already ``dict|null`` shaped).
        - ``str`` (exception/message) becomes ``{"message": ..., "suggestions": ...}``
          with ``suggestions`` as ``None`` when disabled else ``[]``.
        - Any other caller payload becomes ``{"message": str(value), "suggestions": ...}``
          so the ``error`` field factory is always a dictionary or ``None``.
        """
        from cmd_router.lib.commands import CmdParse

        if value is None or value is _UNSET:
            return None
        if isinstance(value, CmdParse.Error):
            return value.to_dict()
        if isinstance(value, dict):
            return value
        if flags.no_suggestions:
            wrapped_suggestions: list[str] | None = None
        else:
            wrapped_suggestions = []
        if isinstance(value, str):
            return {"message": value, "suggestions": wrapped_suggestions}
        return {"message": str(value), "suggestions": wrapped_suggestions}

    def _all_data(self, response_only: bool = False) -> dict[str, Any]:
        value: Any = None if self.value is _UNSET else self.value
        message: str | None = self.message or None
        if response_only:
            return {
                "ok": self.ok,
                "input": self.input,
                "value": value,
                "suggestions": self.suggestions,
                "error": self._transport_value(self.error_payload),
                "message": message,
            }
        return {
            "ok": self.ok,
            "code": self.code.name,
            "kind": str(self.kind),
            "input": self.input,
            "command": self.command,
            "value": value,
            "parsed_args": dict(self.context.args) if self.context is not None else None,
            "error": self.error.to_dict() if self.error is not None else None,
            "message": message,
            "exception": self.exception,
        }


@dataclass(frozen=True, slots=True)
class ControlInitialization:
    """Describe fixture setup and grammar-compilation status.

    ``command_count`` is populated on successful grammar compilation.  Fixture
    failures use the centralized ``ControlFixtureError`` code, while malformed
    setup or grammar values use the corresponding control initialization code.
    The object is intentionally small, so it can be returned directly from the
    module-level API and serialized with ``to_dict``.
    """

    ok: bool
    code: Status
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
            "code": self.code.name,
            "message": self.message,
            "command_count": self.command_count,
        }
        if self.exception is not None:
            data["exception"] = self.exception
        return data

    as_dict = to_dict
