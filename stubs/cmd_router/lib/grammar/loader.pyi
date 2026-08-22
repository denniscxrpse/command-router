from cmd_router.lib.grammar.parsers import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from pathlib import Path

__all__ = ["load_grammars"]

def load_grammars(path: Path) -> tuple[_Dict, _Dict] | int: ...
