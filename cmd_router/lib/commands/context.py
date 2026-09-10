#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "CommandContext",
    "ParseError",
    "ParseErrorKinds",
    "ParseResult",
    "cmd_ctx",
)

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

from cmd_router.lib.control.api.result import ControlResultKinds
from cmd_router.suggestions.algo import fuzzy_str_match
from cmd_router.utils.cli import *
from cmd_router.utils.status import *

_Handler = Callable[..., Any]


@dataclass
class _CommandContext:
    """Namespace reserved for shared command-context helpers."""

    ...


cmd_ctx: Final[_CommandContext] = _CommandContext()
ParseErrorKinds: Final[type[ControlResultKinds]] = ControlResultKinds
"""Alias for the ``ControlResultKinds`` enum."""


@dataclass(frozen=True, slots=True)
class CommandContext:
    """The input and arguments captured by a successful parse."""

    input: str
    args: dict[str, Any]
    cursor: int
    tokens: tuple[str, ...]

    @property
    def original_input(self) -> str:
        """Return the complete command string used for parsing."""
        return self.input

    @property
    def parsed_args(self) -> dict[str, Any]:
        """Return the arguments captured along the successful path."""
        return self.args

    def get(self, name: str, default: Any = None) -> Any:
        """Read a named argument without exposing a ``KeyError``."""
        return self.args.get(name, default)


@dataclass(frozen=True, slots=True)
class ParseError:
    """The furthest failure encountered while traversing the command tree."""

    kind: ParseErrorKinds
    token_index: int
    expected: tuple[str, ...] = ()
    message: str = ""
    partial_args: dict[str, Any] = field(default_factory=dict)
    code: Status | None = None
    token: str | None = None

    @property
    def position(self) -> int:
        """Alias for the token index at which parsing stopped."""
        return self.token_index

    @property
    def expectations(self) -> tuple[str, ...]:
        """Alias useful to callers that prefer the noun form."""
        return self.expected

    @property
    def cursor(self) -> int:
        """Alias for the token cursor at which parsing failed."""
        return self.token_index

    @property
    def parsed_args(self) -> dict[str, Any]:
        """Return the arguments captured before the failure."""
        return dict(self.partial_args)

    def to_dict(self) -> dict[str, Any]:
        """Return the failure details in a transport-friendly mapping.

        Always contains every key and uses plain JSON-serializable values:
        ``kind`` and ``code`` are strings (or ``None``), ``expected`` is a
        list, ``token`` is the unmatched fragment (or ``None`` for incomplete
        input), ``suggestions`` is the ranked hint list (or ``None`` when
        ``flags.no_suggestions`` disables hints), and an empty ``message``
        is returned as ``None`` so consumers see a fixed shape in both
        dictionaries and JSON.
        """
        return {
            "kind": str(self.kind),
            "token_index": self.token_index,
            "expected": list(self.expected),
            "token": self.token,
            "suggestions": self._get_suggestions(),
            "message": self.message or None,
            "partial_args": dict(self.partial_args),
            "code": self.code.name if self.code is not None else None,
        }

    as_dict = to_dict

    def _get_suggestions(self) -> list[str] | None:
        """Return ranked hints from ``self.expected`` via ``fuzzy_str_match``.

        Limit is ``suggestions_set_current_size`` (``SUGGESTIONS_MAX`` when
        ``flags.max_sized_suggestions``); ``None`` when ``flags.no_suggestions``.
        """
        if flags.no_suggestions:
            return None
        try:
            from cmd_router.lib.control.api.fittings import FixturesSetup

            limit = FixturesSetup._resolve_suggestions_limit()
        except Exception:
            from cmd_router.utils.cli import flags as _flags
            from cmd_router.utils.context import uctx as _uctx

            limit = _uctx.SUGGESTIONS_MAX if _flags.max_sized_suggestions else 5
        if limit <= 0:
            return []
        pool: list[str] = list(self.expected)
        if not pool:
            return []
        token = self.token
        return fuzzy_str_match(token, pool, limit)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Either a handler/context pair or a structured parse failure."""

    handler: _Handler | None = None
    context: CommandContext | None = None
    error: ParseError | None = None

    @property
    def ok(self) -> bool:
        """Whether parsing reached a node with a handler."""
        return self.handler is not None and self.context is not None and self.error is None

    @property
    def success(self) -> bool:
        """Readable alias for ``ok``."""
        return self.ok
