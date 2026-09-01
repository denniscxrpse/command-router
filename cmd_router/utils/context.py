#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Shared constants and paths used by the commands-router packages.

``uctx`` is deliberately not a mutable commands configuration object.  It
provides schema constants, serialized grammar keys, and a read-only listener
for the latest stderr message; fixture-owned settings such as ``cmd_prefix``,
the help policy, action functions, and argument overrides live on
``FixturesSetup`` instances in the control API.  Keeping commands settings out
of this module avoids hidden global state between independent control surfaces
and fixture initializations.
"""

__all__ = (
    "paths",
    "Error",
    "error",
    "uctx",
)

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final, final
from warnings import deprecated


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
    FIXTURES_HTTP: Path = FIXTURES / "http"
    LOGS_DIR: Path = ROOT / "logs"


@final
@deprecated("Use `Error` object instead of `Error` enum.")
class Error(IntEnum):
    def __str__(self) -> str:
        return self.name

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
        """Describe why an argument value could not be parsed."""

        message: str
        expected: str


@dataclass(frozen=True, slots=True)
class _UniversalContext:
    """Namespace containing shared constants and read-only observations."""

    # Constant values used while validating grammar files.
    VALID_SCHEMAS: Final[frozenset[int]] = frozenset({1})
    "The valid schemas for the grammars."

    # Serialized key names used by grammar containers.
    cmd_router: Final[str] = "cmd-router"
    grammar: Final[str] = "grammar"
    schema_version: Final[str] = "schema-version"


paths: Final[_Paths] = _Paths()
error: Final[type[Error]] = Error
uctx: Final[_UniversalContext] = _UniversalContext()
