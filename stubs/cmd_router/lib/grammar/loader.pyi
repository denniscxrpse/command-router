from cmd_router.lib.grammar.parsers import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import StatusType
from pathlib import Path
from typing import Any

__all__ = ["load_grammars"]

_Dict = dict[str, Any]
_DictOrError = _Dict | StatusType

def load_grammars(path: Path) -> tuple[_Dict, _Dict] | StatusType: ...
