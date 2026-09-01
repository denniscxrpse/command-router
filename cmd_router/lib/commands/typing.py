#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Argument types used by command nodes.

Argument types deliberately do one small job: convert one token (or a greedy sequence of tokens assembled by the
dispatcher) into a Python value. Tree traversal and error selection belong to ``dispatcher``.
"""

__all__ = (
    "ArgumentParseError",
    "ArgumentType",
    "GreedyString",
    "Int",
    "String",
    "Word",
    "arg_type",
    "greedy",
    "integer",
    "string",
    "word",
)

from enum import StrEnum, auto
from typing import ClassVar, Final, Generic, TypeVar, final

from cmd_router.utils.context import error

_ValueT = TypeVar("_ValueT")


@final
class _NamedT(StrEnum):
    """Base class for named values."""

    UNSET = auto()
    WORD = auto()
    STR = auto()
    INT = auto()
    GREEDY_STR = auto()


ArgumentParseError = error.ArgumentParseError


class ArgumentType(Generic[_ValueT]):  # noqa: UP046
    """Base class for values accepted by an ``ArgumentNode``."""

    name: ClassVar[_NamedT] = _NamedT.UNSET
    greedy: ClassVar[bool] = False

    def parse(self, value: str) -> _ValueT | ArgumentParseError:
        """Convert *value* into the argument's Python representation."""
        return value  # ty: ignore[invalid-return-type]


@final
class Word(ArgumentType[str]):
    name = _NamedT.WORD


class String(ArgumentType[str]):
    name = _NamedT.STR


@final
class Int(ArgumentType[int]):
    name = _NamedT.INT

    def parse(self, value: str) -> int | ArgumentParseError:
        digits = value[1:] if value[:1] in ("+", "-") else value
        if not digits or any(character not in "0123456789" for character in digits):
            return ArgumentParseError("expected an integer", self.name)
        return int(value)


class GreedyString(String):
    name = _NamedT.GREEDY_STR
    greedy = True


def word() -> ArgumentType[str]:
    """Return an argument type that consumes one token as text."""
    return Word()


def string() -> ArgumentType[str]:
    """Return an argument type that consumes one token as text."""
    return String()


def integer() -> ArgumentType[int]:
    """Return an argument type that accepts signed decimal integers."""
    return Int()


def greedy() -> ArgumentType[str]:
    """Return an argument type that consumes the rest of the command."""
    return GreedyString()


arg_type: Final[ArgumentType[str]] = ArgumentType()
