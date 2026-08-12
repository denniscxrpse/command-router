#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Live state exposed by the control API."""

from collections.abc import Callable
from types import ModuleType
from typing import Any, Final

from cmd_router.lib.command import CmdNode
from cmd_router.utils.context import ctx

from .result import ControlInitialization, ControlResult

_Action = Callable[..., Any]


class _DeeperLevelContext:
    """Expose live dispatcher and fixture state to Python callers."""

    def __init__(self, command_context: Any = ctx) -> None:
        """Create a control context backed by *command_context*."""
        self.context = command_context
        self.dispatcher = CmdNode.Dispatcher()
        self.grammars: dict[str, str] = {}
        self.fixture_module: ModuleType | None = None
        self.fixture_logic: Any = None
        self.initialized = False
        self.last_result: ControlResult | None = None
        self.last_initialization: ControlInitialization | None = None

    @property
    def command_args_ctrl(self) -> dict[str, Any]:
        """Return the command argument overrides."""
        return self.context.command_args_ctrl

    @command_args_ctrl.setter
    def command_args_ctrl(self, value: dict[str, Any]) -> None:
        """Replace the command argument overrides."""
        if not isinstance(value, dict):
            raise TypeError("command_args_ctrl must be a dictionary")
        self.context.command_args_ctrl = value

    @property
    def command_action(self) -> dict[str, _Action]:
        """Return the command action mapping."""
        return self.context.command_action

    @command_action.setter
    def command_action(self, value: dict[str, _Action]) -> None:
        """Replace the command action mapping."""
        if not isinstance(value, dict):
            raise TypeError("command_action must be a dictionary")
        self.context.command_action = value

    def set_command_args(self, command: str, **arguments: Any) -> None:
        """Set runtime argument overrides for one command."""
        if not isinstance(command, str) or not command:
            raise ValueError("command must be a non-empty string")
        overrides = self.command_args_ctrl.setdefault(command, {})
        if not isinstance(overrides, dict):
            raise TypeError(f"argument overrides for {command!r} must be a dictionary")
        overrides.update(arguments)

    def clear_command_args(self, command: str | None = None) -> None:
        """Clear one command's overrides, or all overrides."""
        if command is None:
            self.command_args_ctrl.clear()
        else:
            self.command_args_ctrl.pop(command, None)


DeeperLevelContext: Final[type[_DeeperLevelContext]] = _DeeperLevelContext
