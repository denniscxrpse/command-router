from .context import *
from .control import *
from .result import *
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final

__all__ = ["Api"]

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
    def get_latest_stderr() -> str: ...
    def readable_stderr(self) -> dict[str, Any] | None: ...

@dataclass(frozen=True)
class Api:
    Control: Final[Control] = ...
    Surface: Final[_ControlSurface] = ...
    Context: Final[ControlDeeperContext] = ...
