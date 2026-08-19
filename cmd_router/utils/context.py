#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Shared constants and paths used by the command-router packages.

``uctx`` is deliberately not a mutable command configuration object.  Its
``c`` and ``k`` namespaces provide schema constants and serialized grammar
keys; fixture-owned settings such as ``cmd_prefix``, the help policy, action
functions, and argument overrides live on ``FixturesSetup`` instances in the
control API.  Keeping this module limited to constants avoids a hidden global
state between independent control surfaces and fixture initializations.
"""

__all__ = (
    "paths",
    "error",
    "uctx",
    "uctx_c",
    "uctx_k",
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
    FIXTURES_HTTP: Path = FIXTURES / "http"
    LOGS_DIR: Path = ROOT / "logs"


class _Error(IntEnum):
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
    """Namespace containing constants only; no command settings are stored here."""

    # noinspection pep8-naming
    class c:
        """Constant values used while validating grammar files."""

        EMPTY_STR: Final[str] = ""
        "Yeah, literally. This is meant for readability."
        VALID_SCHEMAS: Final[frozenset[int]] = frozenset({1})
        "The valid schemas for the grammars."

    # noinspection pep8-naming
    class k:
        """Serialized key names used by grammar containers."""

        cmd_router: Final[str] = "cmd-router"
        grammar: Final[str] = "grammar"
        schema_version: Final[str] = "schema-version"


paths: Final[_Paths] = _Paths()
error: Final[type[_Error]] = _Error

uctx: Final[_UniversalContext] = _UniversalContext()
uctx_c: Final[type[_UniversalContext.c]] = uctx.c
uctx_k: Final[type[_UniversalContext.k]] = uctx.k
