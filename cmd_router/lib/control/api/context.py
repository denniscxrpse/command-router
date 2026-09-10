#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Live state and configuration exposed by the control API.

``ControlDeeperContext`` is the inspection and runtime-override surface behind
``Control``.  It owns one ``FixturesSetup`` instance, the compiled dispatcher,
the grammar mapping used to build that dispatcher, and the most recent results.
The setup object is deliberately per-control: settings no longer live on the
process-wide ``uctx`` constants object.

The control lifecycle replaces ``fixture_setup`` when a fixture is initialized.
Before that happens, a private default ``FixturesSetup`` provides the normal
prefix, help policy, empty action mapping, and empty argument-override mapping
so direct programmatic use of ``Control`` remains possible without a fixture.
supported way to inspect or change live configuration after initialization.
The public properties in this module delegate to the active setup and are the

Argument overrides are separate from grammar compilation.  They are applied
to parsed arguments immediately before an action runs, so ``set_command_args``
can change behavior without rebuilding the dispatcher. The action mapping
is also live: compiler-generated handlers look up actions through the active
setup when invoked.
"""

__all__ = ("ControlDeeperContext",)

from collections.abc import Callable
from types import ModuleType
from typing import Any, final

from cmd_router.lib.commands import CmdNode
from cmd_router.lib.commands.dispatcher import CommandDispatcher
from cmd_router.utils import log

from .fittings import FixturesSetup
from .result import ControlInitialization, ControlResult

_Action = Callable[..., Any]


@final
class ControlDeeperContext:
    """Expose live dispatcher, fixture, setup, and execution state.

    A caller may construct with a ``FixturesSetup`` for isolated configuration,
    or omit the setup to receive a fresh default setup backed by a harmless
    placeholder logic object.

    ``fixture_module`` and ``fixture_logic`` are populated only after a
    successful fixture initialization.  ``fixture_setup`` is the corresponding
    configuration object.  The ``context`` property is retained as a concise
    compatibility alias for that setup.
    """

    def __init__(self, setup: FixturesSetup | None = None) -> None:
        """Create a live control state backed by *setup* or fresh defaults."""
        if setup is not None and not isinstance(setup, FixturesSetup):
            raise TypeError(f"setup must be a {FixturesSetup.__qualname__} instance")
        self._setup = setup if setup is not None else FixturesSetup(logic=object())
        self.dispatcher: CommandDispatcher = CmdNode.Dispatcher()
        self.grammars: dict[str, str] = {}
        self.fixture_module: ModuleType | None = None
        self.fixture_logic: Any = None
        self.initialized: bool = False
        self.last_result: ControlResult | None = None
        self.last_initialization: ControlInitialization | None = None
        log.debug("deeper control state created (custom_setup=%s)", setup is not None)

    @property
    def setup(self) -> FixturesSetup:
        """Return the active fixture-owned configuration object."""
        return self._setup

    @property
    def context(self) -> FixturesSetup:
        """Return ``setup`` through the historical context alias."""
        return self._setup

    @context.setter
    def context(self, value: FixturesSetup) -> None:
        """Replace the active setup through the compatibility alias."""
        self._replace_setup(value)

    @property
    def fixture_setup(self) -> FixturesSetup:
        """Return the setup associated with the current fixture or defaults."""
        return self._setup

    def _replace_setup(self, value: FixturesSetup) -> None:
        """Validate and install a new active setup."""
        if not isinstance(value, FixturesSetup):
            raise TypeError("setup must be a FixturesSetup instance")
        self._setup = value
        log.info("active fixture setup replaced (%s)", type(value).__name__)

    def attach_fixture(self, module: ModuleType, logic: Any, setup: FixturesSetup) -> None:
        """Store a successfully initialized fixture and make its setup active."""
        if not isinstance(module, ModuleType):
            raise TypeError("fixture module must be a module")
        if not isinstance(setup, FixturesSetup):
            raise TypeError("fixture setup must be a FixturesSetup instance")
        self._setup = setup
        self.fixture_module = module
        self.fixture_logic = logic
        log.info("attached fixture %s with setup %s", module.__name__, type(setup).__name__)

    @property
    def cmd_prefix(self) -> str:
        """Return the active command prefix."""
        return self._setup.cmd_prefix

    @cmd_prefix.setter
    def cmd_prefix(self, value: str) -> None:
        """Update the active setup's command prefix."""
        self._setup.cmd_prefix = value

    @property
    def lazy_init_help(self) -> bool:
        """Return the active setup's built-in-help policy."""
        return self._setup.lazy_init_help

    @lazy_init_help.setter
    def lazy_init_help(self, value: bool) -> None:
        """Update the active setup's built-in-help policy."""
        self._setup.lazy_init_help = value

    @property
    def command_args_ctrl(self) -> dict[str, Any]:
        """Return live command argument overrides from the active setup."""
        return self._setup.command_args_ctrl

    @command_args_ctrl.setter
    def command_args_ctrl(self, value: dict[str, Any]) -> None:
        """Replace command argument overrides on the active setup."""
        self._setup.command_args_ctrl = value

    @property
    def command_action(self) -> dict[str, _Action]:
        """Return the live action mapping from the active setup."""
        return self._setup.command_action

    @command_action.setter
    def command_action(self, value: dict[str, _Action]) -> None:
        """Replace the active setup's action mapping."""
        self._setup.command_action = value

    def set_command_args(self, command: str, **arguments: Any) -> None:
        """Set runtime argument overrides for one command.

        Overrides are merged into the parsed arguments immediately before the
        action is called.  A command-specific mapping takes precedence over
        parsed values, and a flat entry whose key matches a parsed argument is
        also accepted for small integrations.

        :raises ValueError: If *command* is not a non-empty string.
        :raises TypeError: If an existing command entry is not a mapping.
        """
        if not isinstance(command, str) or not command:
            raise ValueError("command must be a non-empty string")
        overrides = self.command_args_ctrl.setdefault(command, {})
        if not isinstance(overrides, dict):
            raise TypeError(f"argument overrides for {command!r} must be a dictionary")
        overrides.update(arguments)
        log.debug("set %d argument override(s) for %r", len(arguments), command)

    def clear_command_args(self, command: str | None = None) -> None:
        """Clear one command's overrides, or all active setup overrides."""
        if command is None:
            self.command_args_ctrl.clear()
            log.debug("cleared all command argument overrides")
        else:
            self.command_args_ctrl.pop(command, None)
            log.debug("cleared argument overrides for %r", command)
