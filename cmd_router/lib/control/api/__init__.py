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
``ControlDeeperContext`` is the inspection surface for the live dispatcher,
fixture objects, configuration, argument overrides, and last results.  The

Module-level ``control`` and ``deeper_level`` values provide one shared
application surface for simple integrations.  Use ``Control`` directly when
an application needs an isolated state or more than one independently configured
command surface.

The old mutable ``uctx`` settings are not part of this API.  ``uctx`` remains
available only for shared constants and schema keys; command settings must be
read from or written through a ``FixturesSetup``/``ControlDeeperContext``.
"""

__all__ = ["Api"]


import ast
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Final, final

from cmd_router.utils.cli import flags
from cmd_router.utils.logger import log

from .context import *
from .control import *
from .result import *


@final
class _ControlSurface:
    """Convenience methods for accessing the shared control surface. Also includes tooling for testing."""

    @staticmethod
    def initialize(
        grammars: Mapping[str, str] | None = None,
        *,
        fixture: ModuleType | str | Path | None = None,
        keep_help: bool | None = None,
    ) -> ControlInitialization:
        """Initialize the shared control surface from grammars and an optional fixture.

        See ``Control.initialize`` for fixture discovery, setup binding, help
        policy, and structured failure behavior.
        """
        return control.initialize(grammars, fixture=fixture, keep_help=keep_help)

    @staticmethod
    def execute(command: Any) -> ControlResult:
        """Execute *command* through the shared control surface."""
        return control.execute(command)

    @staticmethod
    async def execute_async(command: Any) -> ControlResult:
        """Execute *command* asynchronously through the shared control surface."""
        return await control.execute_async(command)

    @staticmethod
    def get_latest_stderr() -> str:
        """Return the latest message emitted through the ``stderr`` writer."""
        return log.stderr.latest_call

    def readable_stderr(self) -> dict[str, Any] | None:
        """Return the latest message emitted through the ``stderr`` writer as a dictionary like object.

        It is assumed that the message is a valid JSON string, invalid initialization of the API will result in a
        ``None`` return value and a lot of ``ERROR`` level messages.
        """
        j: dict[str, Any] | None
        try:
            if flags.json_out:
                return json.loads(self.get_latest_stderr())
            j = ast.literal_eval(self.get_latest_stderr())
        except ValueError, SyntaxError, TypeError, json.JSONDecodeError:
            log.error("failed to parse listener output. stderr output might be impossible to parse.")
            j = None
        return j


@dataclass(frozen=True)
class Api:
    """Convenience namespace for accessing the shared control surface."""

    Control: Final[Control] = control
    Surface: Final[_ControlSurface] = _ControlSurface()
    Context: Final[ControlDeeperContext] = control.deeper_context
