from _typeshed import Incomplete
from enum import StrEnum
from typing import ClassVar, Final, Generic, TypeVar

__all__ = [
    "ArgumentParseError",
    "ArgumentType",
    "Word",
    "String",
    "Int",
    "GreedyString",
    "word",
    "string",
    "integer",
    "greedy",
    "arg_type",
]

_ValueT = TypeVar("_ValueT")

class _NamedT(StrEnum):
    UNSET = ...
    WORD = ...
    STR = ...
    INT = ...
    GREEDY_STR = ...

ArgumentParseError: Incomplete

class ArgumentType(Generic[_ValueT]):
    name: ClassVar[_NamedT]
    greedy: ClassVar[bool]
    def parse(self, value: str) -> _ValueT | object: ...
    @property
    def is_greedy(self) -> bool: ...
    @property
    def get_name(self) -> str: ...

class Word(ArgumentType[str]):
    name: Incomplete

class String(ArgumentType[str]):
    name: Incomplete

class Int(ArgumentType[int]):
    name: Incomplete
    def parse(self, value: str) -> int | ArgumentParseError: ...

class GreedyString(String):
    name: Incomplete
    greedy: bool

def word() -> ArgumentType[str]: ...
def string() -> ArgumentType[str]: ...
def integer() -> ArgumentType[int]: ...
def greedy() -> ArgumentType[str]: ...

arg_type: Final[ArgumentType[str]]
