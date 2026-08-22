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

from typing import ClassVar, Final, Generic, TypeVar

from cmd_router.utils.context import error

_ValueT = TypeVar("_ValueT")

ArgumentParseError = error.ArgumentParseError


class _ArgType(Generic[_ValueT]):  # noqa: UP046
    """Base class for values accepted by an ``ArgumentNode``."""

    name: ClassVar[str] = "string"
    greedy: ClassVar[bool] = False

    def parse(self, value: str) -> _ValueT | ArgumentParseError:
        """Convert *value* into the argument's Python representation."""
        return value  # type: ignore[return-value]


class _WordType(_ArgType[str]):
    name = "word"


class _StringType(_ArgType[str]):
    name = "string"


class _IntegerType(_ArgType[int]):
    name = "int"

    def parse(self, value: str) -> int | ArgumentParseError:
        digits = value[1:] if value[:1] in ("+", "-") else value
        if not digits or any(character not in "0123456789" for character in digits):
            return ArgumentParseError("expected an integer", self.name)
        return int(value)


class _GreedyStringType(_StringType):
    name = "greedy_string"
    greedy = True


ArgumentType = _ArgType
Word = _WordType
String = _StringType
Int = _IntegerType
GreedyString = _GreedyStringType

arg_type: Final[ArgumentType[str]] = ArgumentType()


def word() -> ArgumentType[str]:
    """Return an argument type that consumes one token as text."""
    return _WordType()


def string() -> ArgumentType[str]:
    """Return an argument type that consumes one token as text."""
    return _StringType()


def integer() -> ArgumentType[int]:
    """Return an argument type that accepts signed decimal integers."""
    return _IntegerType()


def greedy() -> ArgumentType[str]:
    """Return an argument type that consumes the rest of the command."""
    return _GreedyStringType()
