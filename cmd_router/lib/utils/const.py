__all__ = ("const", "paths", "errc",)

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final, final


@final
class Const:
    @dataclass
    class Paths:
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
        GRAMMARS: Path = FIXTURES / "grammars.toml"
        LOGS_DIR: Path = ROOT / "logs"

    class ErrCodes(IntEnum):
        Abort = -1
        Succeed = 0
        DefaultGrammarError = 1
        GrammarLoadError = 2
        InvalidGrammarError = 3
        UnsupportedGrammarFormatError = 4


const: Final[Const] = Const()
paths: Final[Const.Paths] = const.Paths()
errc: Final[type[Const.ErrCodes]] = const.ErrCodes
