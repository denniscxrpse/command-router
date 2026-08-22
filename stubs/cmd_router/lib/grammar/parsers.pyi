from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from collections.abc import Callable
from pathlib import Path
from typing import Final

__all__ = ["grammar_parsers"]

grammar_parsers: Final[dict[str, Callable[[Path], _DictOrError]]]
