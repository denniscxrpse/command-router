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

from cmd_router.utils import stat

_ValueT = TypeVar("_ValueT")


@final
class _NamedT(StrEnum):
    """Base class for named values."""

    UNSET = auto()
    WORD = auto()
    STR = auto()
    INT = auto()
    GREEDY_STR = auto()


ArgumentParseError = stat.ArgumentParseError


class ArgumentType(Generic[_ValueT]):  # noqa: UP046
    """Base class for values accepted by an ``ArgumentNode``."""

    name: ClassVar[_NamedT] = _NamedT.UNSET
    greedy: ClassVar[bool] = False

    def parse(self, value: str) -> _ValueT | object:
        """Convert *value* into the argument's Python representation."""
        return value

    @property
    def is_greedy(self) -> bool:
        """Whether this argument consumes the rest of the command."""
        return self.greedy

    @property
    def get_name(self) -> str:
        """Return the name of this argument type."""
        return self.name.value


@final
class Word(ArgumentType[str]):
    name = _NamedT.WORD


class String(ArgumentType[str]):
    name = _NamedT.STR


@final
class Int(ArgumentType[int]):
    name = _NamedT.INT

    def parse(self, value: str) -> int | ArgumentParseError:
        """Convert *value* into an integer.

        Returns an ``ArgumentParseError`` if the value is not a valid integer.
        """
        # value.startswith is optimized in C and more readable
        digits = value[1:] if value.startswith(("+", "-")) else value

        # isascii() ensures strictly 0-9, rejecting unicode numbers
        # isdecimal() ensures they are valid base-10 numbers
        if not digits or not digits.isascii() or not digits.isdecimal():
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
