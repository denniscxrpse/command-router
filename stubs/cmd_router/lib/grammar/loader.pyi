from pathlib import Path
from typing import Any

from cmd_router.lib.grammar.parsers import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *

__all__ = ["load_grammars"]

_Dict = dict[str, Any]
_DictOrError = _Dict | int

def load_grammars(path: Path) -> tuple[_Dict, _Dict] | int: ...
