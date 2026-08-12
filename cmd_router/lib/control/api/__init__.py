#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Public control classes and the module-level control surface."""

from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from .context import DeeperLevelContext, _DeeperLevelContext
from .control import Control
from .result import ControlInitialization, ControlResult

__all__ = (
    "Control",
    "ControlInitialization",
    "ControlResult",
    "DeeperLevelContext",
    "control",
    "deeper_level",
    "execute",
    "execute_async",
    "initialize",
)

control: Final[Control] = Control()
deeper_level: Final[_DeeperLevelContext] = control.deeper_level


def initialize(
    grammars: Mapping[str, str] | None = None,
    *,
    fixture: ModuleType | str | Path | None = None,
    keep_help: bool | None = None,
) -> ControlInitialization:
    """Initialize the module-level control surface."""
    return control.initialize(grammars, fixture=fixture, keep_help=keep_help)


def execute(command: Any) -> ControlResult:
    """Execute through the module-level control surface."""
    return control.execute(command)


async def execute_async(command: Any) -> ControlResult:
    """Execute asynchronously through the module-level control surface."""
    return await control.execute_async(command)
