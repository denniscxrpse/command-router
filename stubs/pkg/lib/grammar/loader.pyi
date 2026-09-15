from pathlib import Path
from typing import Any

from pkg.lib.grammar.parsers import *
from pkg.utils import Status

__all__ = ["load_grammars"]

_Dict = dict[str, Any]
_DictOrError = _Dict | Status

def load_grammars(path: Path) -> tuple[_Dict, _Dict] | Status: ...
