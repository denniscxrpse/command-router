#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Public control API, fixture configuration, and module-level convenience calls.

The API is organized around a small lifecycle.  ``Control`` owns one command
surface and compiles grammar mappings into a dispatcher.  ``FixturesSetup``
owns the mutable settings required by that surface, while
``FixturesContextHolder`` is the extension point for fixture state and action
methods.  A fixture module exposes ``context_holder`` and ``SetupFixtures``;
the control layer creates the holder, injects it as ``SetupFixtures.logic``,
and installs the resulting setup before compiling grammars.

``DeeperLevelContext`` is the inspection surface for the live dispatcher,
fixture objects, configuration, argument overrides, and last results.  The
module-level ``control`` and ``deeper_level`` values provide one shared
application surface for simple integrations.  Use ``Control`` directly when
an application needs isolated state or more than one independently configured
command surface.

The old mutable ``uctx`` settings are not part of this API.  ``uctx`` remains
available only for shared constants and schema keys; command settings must be
read from or written through a ``FixturesSetup``/``DeeperLevelContext``.
"""

from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from .context import DeeperLevelContext, _DeeperLevelContext
from .control import Control
from .fixtures import FixturesContextHolder, FixturesSetup
from .result import ControlInitialization, ControlResult

__all__ = (
    "Control",
    "ControlInitialization",
    "ControlResult",
    "DeeperLevelContext",
    "FixturesContextHolder",
    "FixturesSetup",
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
    """Initialize the shared control surface from grammars and an optional fixture.

    See :meth:`Control.initialize` for fixture discovery, setup binding, help
    policy, and structured failure behavior.
    """
    return control.initialize(grammars, fixture=fixture, keep_help=keep_help)


def execute(command: Any) -> ControlResult:
    """Execute *command* through the shared control surface."""
    return control.execute(command)


async def execute_async(command: Any) -> ControlResult:
    """Execute *command* asynchronously through the shared control surface."""
    return await control.execute_async(command)
