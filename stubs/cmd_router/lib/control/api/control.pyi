from cmd_router.utils.cli import *
from cmd_router.utils.logger import *
from .context import *
from .fittings import *
from .result import *
from asyncio import Lock
from cmd_router.lib.commands import CmdParse
from cmd_router.lib.control.compiler import _GrammarSource
from cmd_router.utils.status import Status
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Self

__all__ = ["ControlType", "control"]

_Action = Callable[..., Any]

@dataclass(frozen=True, slots=True)
class _Invocation:
    command: str
    parsed: CmdParse.Result
    context: CmdParse.Context
    handler: _Action

class _Control:
    deeper_context: ControlDeeperContext
    _async_lock: Lock
    _stderr_locked: bool
    def __init__(self, *, setup: FixturesSetup | None = None, deeper: ControlDeeperContext | None = None) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *_arguments: Any) -> None: ...
    @property
    def context(self) -> FixturesSetup: ...
    @property
    def deeper(self) -> ControlDeeperContext: ...
    def initialize(
        self,
        grammars: _GrammarSource | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization: ...
    def configure(self, grammars: _GrammarSource) -> ControlInitialization: ...
    def close(self) -> None: ...
    def execute(self, command: Any) -> ControlResult: ...
    async def execute_async(self, command: Any) -> ControlResult: ...
    dispatch = execute
    dispatch_async = execute_async
    aexecute = execute_async
    def _initialize_fixture(self, fixture: ModuleType | str | Path) -> ControlInitialization: ...
    def _initialization_error(
        self, message: str, exception: Exception | None = None, code: Status = ...
    ) -> ControlInitialization: ...
    def _execute_sync(self, command: Any) -> ControlResult: ...
    def _prepare(self, command: Any) -> ControlResult | _Invocation: ...
    def _controlled_arguments(self, command: str, arguments: Mapping[str, Any]) -> dict[str, Any]: ...
    def _remember(self, result: ControlResult) -> ControlResult: ...

ControlType: type
control: Final[ControlType]
