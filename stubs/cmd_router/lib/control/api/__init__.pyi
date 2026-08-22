from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from .context import DeeperLevelContext as DeeperLevelContext
from .context import _DeeperLevelContext
from .control import Control as Control
from .fixtures import FixturesContextHolder as FixturesContextHolder
from .fixtures import FixturesSetup as FixturesSetup
from .result import ControlInitialization as ControlInitialization
from .result import ControlResult as ControlResult

__all__ = [
    "DeeperLevelContext",
    "Control",
    "FixturesContextHolder",
    "FixturesSetup",
    "ControlInitialization",
    "ControlResult",
    "control",
    "deeper_level",
    "initialize",
    "execute",
    "execute_async",
    "listener",
]

control: Final[Control]
deeper_level: Final[_DeeperLevelContext]

def initialize(
    grammars: Mapping[str, str] | None = None,
    *,
    fixture: ModuleType | str | Path | None = None,
    keep_help: bool | None = None,
) -> ControlInitialization: ...
def execute(command: Any) -> ControlResult: ...
async def execute_async(command: Any) -> ControlResult: ...
def listener() -> str: ...
