from .context import DeeperLevelContext as DeeperLevelContext, _DeeperLevelContext
from .control import Control as Control
from .fixtures import FixturesContextHolder as FixturesContextHolder, FixturesSetup as FixturesSetup
from .result import ControlInitialization as ControlInitialization, ControlResult as ControlResult
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final

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
