from _typeshed import Incomplete
from typing import ClassVar, Final, Generic

__all__ = [
    "ArgumentParseError",
    "ArgumentType",
    "Word",
    "String",
    "Int",
    "GreedyString",
    "arg_type",
    "word",
    "string",
    "integer",
    "greedy",
]

ArgumentParseError: Incomplete

class _ArgType(Generic[_ValueT]):
    name: ClassVar[str]
    greedy: ClassVar[bool]
    def parse(self, value: str) -> _ValueT | ArgumentParseError: ...

class _WordType(_ArgType[str]):
    name: str

class _StringType(_ArgType[str]):
    name: str

class _IntegerType(_ArgType[int]):
    name: str
    def parse(self, value: str) -> int | ArgumentParseError: ...

class _GreedyStringType(_StringType):
    name: str
    greedy: bool

ArgumentType: Incomplete
Word: Incomplete
String: Incomplete
Int: Incomplete
GreedyString: Incomplete
arg_type: Final[ArgumentType[str]]

def word() -> ArgumentType[str]: ...
def string() -> ArgumentType[str]: ...
def integer() -> ArgumentType[int]: ...
def greedy() -> ArgumentType[str]: ...
