#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


__all__ = (
    "CommandContext",
    "ParseError",
    "ParseResult",
    "cmd_context",
)

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

_Handler = Callable[..., Any]


@dataclass
class _Context:
    """Namespace reserved for shared command-context helpers."""

    ...


cmd_context: Final[_Context] = _Context()


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

    kind: str
    token_index: int
    expected: tuple[str, ...] = ()
    message: str = ""
    partial_args: dict[str, Any] = field(default_factory=dict)
    code: int | None = None

    @property
    def position(self) -> int:
        """Alias for the token index at which parsing stopped."""
        return self.token_index

    @property
    def expectations(self) -> tuple[str, ...]:
        """Alias useful to callers that prefer the noun form."""
        return self.expected


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
