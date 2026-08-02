#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "paths",
    "error",
    "ctx",
)

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final


@dataclass
class _Paths:
    @staticmethod
    def _get_root() -> Path:
        """Traverse up to find the project root (containing pyproject.toml)."""
        curr: Path = Path(__file__).resolve().parent
        while curr != curr.parent:
            if (curr / "uv.lock").exists():
                return curr
            curr: Path = curr.parent
        # Fallback to current directory if not found
        return Path.cwd()

    ROOT: Path = _get_root()
    FIXTURES: Path = ROOT / "fixtures"
    LOGS_DIR: Path = ROOT / "logs"


class _ErrorCodes(IntEnum):
    def __str__(self) -> str:
        return self.name

    Abort = -1
    Succeed = 0
    DefaultGrammarError = 1
    GrammarLoadError = 2
    InvalidGrammarError = 3
    UnsupportedGrammarFormatError = 4
    TokenizeError = 5


@dataclass
class _Context:
    empty_str = ""
    "Yeah, literally. This is meant for readability."
    valid_schemas: Final[tuple[int]] = (1,)
    """The valid schemas for the grammars."""


paths: Final[_Paths] = _Paths()
error: Final[type[_ErrorCodes]] = _ErrorCodes
ctx: Final[_Context] = _Context()
