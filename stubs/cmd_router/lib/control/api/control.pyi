from ..compiler import _GrammarSource
from .context import _DeeperLevelContext
from .fixtures import FixturesSetup
from .result import ControlInitialization, ControlResult
from cmd_router.lib.command import CmdParse
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Self

__all__ = ["Control"]

@dataclass(frozen=True, slots=True)
class _Invocation:
    command: str
    parsed: CmdParse.Result
    context: CmdParse.Context
    handler: _Action

class Control:
    deeper_level: _DeeperLevelContext
    def __init__(self, *, setup: FixturesSetup | None = None, deeper: _DeeperLevelContext | None = None) -> None: ...
    @property
    def context(self) -> FixturesSetup: ...
    @property
    def deeper(self) -> _DeeperLevelContext: ...
    def initialize(
        self,
        grammars: _GrammarSource | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization: ...
    def configure(self, grammars: _GrammarSource) -> ControlInitialization: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *_arguments: Any) -> None: ...
    def execute(self, command: Any) -> ControlResult: ...
    dispatch = execute
    async def execute_async(self, command: Any) -> ControlResult: ...
    async_dispatch = execute_async
    aexecute = execute_async
