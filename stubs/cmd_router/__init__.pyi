from cmd_router.lib.grammar.loader import *
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from _typeshed import Incomplete
from cmd_router.api import (
    Control as Control,
    ControlInitialization as ControlInitialization,
    ControlResult as ControlResult,
)
from pathlib import Path
from typing import Any

__all__ = ["Control", "ControlInitialization", "ControlResult", "init_flags", "CommandRouter", "_Handler@60"]

class _CmdRouter:
    grammars: _Dict
    info: _Dict
    control: Incomplete
    def normalize(self, t: tuple[_Dict, _Dict]) -> None: ...
    def lazy_init(self) -> None: ...
    def grammar_init(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | int: ...
    def control_init(self) -> bool: ...

class CommandRouter:
    control: Incomplete
    def __init__(self) -> None: ...
    def execute(self, command: Any) -> ControlResult: ...
    async def execute_async(self, command: Any) -> ControlResult: ...
    @property
    def deeper_level(self) -> Any: ...

# Names in __all__ with no definition:
#   _Handler@60
#   init_flags
