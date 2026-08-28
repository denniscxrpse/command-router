from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final

__all__ = ["Error", "paths", "error", "uctx"]

@dataclass
class _Paths:
    @staticmethod
    def _get_root() -> Path: ...
    ROOT: Path = ...
    FIXTURES: Path = ...
    FIXTURES_HTTP: Path = ...
    LOGS_DIR: Path = ...

class Error(IntEnum):
    def __str__(self) -> str: ...
    Abort = -1
    Succeed = 0
    DefaultGrammarError = 1
    GrammarLoadError = 2
    InvalidGrammarError = 3
    UnsupportedGrammarFormatError = 4
    TokenizeInvalidError = 5
    TokenizeUnsupportedTypeError = 6
    ControlNotInitializedError = 7
    ControlFixtureError = 8
    ControlGrammarError = 9
    ControlActionError = 10
    Interrupted = 18
    @dataclass(frozen=True, slots=True)
    class ArgumentParseError:
        message: str
        expected: str

@dataclass(frozen=True, slots=True)
class _UniversalContext:
    VALID_SCHEMAS: Final[frozenset[int]] = ...
    cmd_router: Final[str] = ...
    grammar: Final[str] = ...
    schema_version: Final[str] = ...

paths: Final[_Paths]
error: Final[type[Error]]
uctx: Final[_UniversalContext]
