from .context import *
from .control import *
from .result import *
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final

__all__ = ["control", "surface", "deeper_level"]

class _ControlSurface:
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

surface: Final[_ControlSurface]
deeper_level: Final[ControlDeeperContext]

# Names in __all__ with no definition:
#   control
