from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import Status
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

__all__ = ["grammar_parsers"]

_Dict = dict[str, Any]
_DictOrError = _Dict | Status
_Tstr = tuple[str, ...]
grammar_parsers: Final[dict[str, Callable[[Path], _DictOrError]]]
