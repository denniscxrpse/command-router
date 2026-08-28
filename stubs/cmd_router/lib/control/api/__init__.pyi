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
    "ControlResultKinds",
    "ControlResult",
    "ControlInitialization",
    "api_symlink",
    "control",
    "deeper_level",
]

class QuickAccess:
    @staticmethod
    def initialize(
        grammars: Mapping[str, str] | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization: ...
    @staticmethod
    def execute(command: Any) -> ControlResult: ...
    @staticmethod
    async def execute_async(command: Any) -> ControlResult: ...
    @staticmethod
    def listener() -> str: ...
    def readable_listener(self) -> dict[str, Any] | None: ...

api_symlink: Final[QuickAccess]
control: Final[Control]
deeper_level: Final[DeeperLevelContext]

# Names in __all__ with no definition:
#   Control
#   ControlInitialization
#   ControlResult
#   ControlResultKinds
#   DeeperLevelContext
#   FixturesContextHolder
#   FixturesSetup
