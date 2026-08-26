from .context import *
from .control import *
from .fixtures import *
from .result import *
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final

__all__ = [
    "DeeperLevelContext",
    "Control",
    "FixturesContextHolder",
    "FixturesSetup",
    "ControlResult",
    "ControlInitialization",
    "control",
    "deeper_level",
    "initialize",
    "execute",
    "execute_async",
    "listener",
    "readable_listener",
]

control: Final[Control]
deeper_level: Final[DeeperLevelContext]

def initialize(
    grammars: Mapping[str, str] | None = None,
    *,
    fixture: ModuleType | str | Path | None = None,
    keep_help: bool | None = None,
) -> ControlInitialization: ...
def execute(command: Any) -> ControlResult: ...
async def execute_async(command: Any) -> ControlResult: ...
def listener() -> str: ...
def readable_listener() -> dict[str, Any] | None: ...

# Names in __all__ with no definition:
#   Control
#   ControlInitialization
#   ControlResult
#   DeeperLevelContext
#   FixturesContextHolder
#   FixturesSetup
