from pathlib import Path
from typing import Any

from _typeshed import Incomplete

from cmd_router.api import (
    Control as Control,
)
from cmd_router.api import (
    ControlInitialization as ControlInitialization,
)
from cmd_router.api import (
    ControlResult as ControlResult,
)
from cmd_router.lib.grammar.loader import *
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *

__all__ = ["Control", "ControlInitialization", "ControlResult", "CommandRouter", "_Handler@59"]

_Dict = dict[str, Any]

class _CmdRouter:
    grammars: _Dict
    info: _Dict
    control: Incomplete
    def normalize(self, t: tuple[_Dict, _Dict]) -> None: ...
    def lazy_init(self) -> None: ...
    def grammar_init(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | int: ...
    def control_init(self) -> bool: ...

class CommandRouter:
    _grammars: Incomplete
    _info: Incomplete
    control: Incomplete
    def __init__(self) -> None: ...
    def execute(self, command: Any) -> ControlResult: ...
    async def execute_async(self, command: Any) -> ControlResult: ...
    @property
    def deeper_level(self) -> Any: ...
    def _control_loop(self) -> int: ...

# Names in __all__ with no definition:
#   _Handler@59
