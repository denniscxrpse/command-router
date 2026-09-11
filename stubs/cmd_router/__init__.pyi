from pathlib import Path
from typing import Any

from _typeshed import Incomplete

from cmd_router.lib.control import ControlResult
from cmd_router.lib.control.api import *
from cmd_router.lib.grammar.loader import *
from cmd_router.suggestions import *
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.lazy_server import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import Status

__all__ = ["CommandRouter", "Lazy@60"]

_Dict = dict[str, Any]

class _CmdRouter:
    grammars: _Dict
    info: _Dict
    control: Incomplete
    def normalize(self, *t: _Dict) -> None: ...
    def lazy_init(self) -> None: ...
    def grammar_init(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | Status: ...
    def control_init(self) -> bool: ...

class CommandRouter:
    _was_i_initialized: bool
    _grammars: Incomplete
    _info: Incomplete
    control: Incomplete
    def __init__(self) -> None: ...
    @property
    def initialize(self) -> Status: ...
    @property
    def main(self) -> Status: ...
    def execute(self, command: Any) -> ControlResult: ...
    async def execute_async(self, command: Any) -> ControlResult: ...
    @property
    def deeper_level(self) -> Any: ...
    def _test_suite_loop(self) -> Status: ...

# Names in __all__ with no definition:
#   Lazy@60
