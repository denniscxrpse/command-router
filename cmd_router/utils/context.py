#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "paths",
    "error",
    "ctx",
)

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Final


@dataclass
class _Paths:
    @staticmethod
    def _get_root() -> Path:
        """Traverse up to find the project root (containing pyproject.toml)."""
        curr: Path = Path(__file__).resolve().parent
        while curr != curr.parent:
            if (curr / "uv.lock").exists():
                return curr
            curr: Path = curr.parent
        # Fallback to current directory if not found
        return Path.cwd()

    ROOT: Path = _get_root()
    FIXTURES: Path = ROOT / "fixtures"
    LOGS_DIR: Path = ROOT / "logs"


class _ErrorCodes(IntEnum):
    def __str__(self) -> str:
        return self.name

    Abort = -1
    Succeed = 0
    DefaultGrammarError = 1
    GrammarLoadError = 2
    InvalidGrammarError = 3
    UnsupportedGrammarFormatError = 4
    TokenizeInvalidError = 5
    TokenizeUnsupportedTypeError = 6
    ControlNotInitializedError = 7
    ControlFixtureError = 8
    ControlGrammarError = 9
    ControlActionError = 10


@dataclass
class _Context:
    # noinspection pep8-naming
    class c:
        """`Constants` namespace. We use ``c`` for quick access to these."""

        EMPTY_STR: Final[str] = ""
        "Yeah, literally. This is meant for readability."
        VALID_SCHEMAS: Final[frozenset[int]] = frozenset({1})
        "The valid schemas for the grammars."

    # Values that can be set externally:
    cmd_prefix: str = "/"
    """The prefix for all commands.

    Any input that does not start with this prefix is treated as greedy (non-command) input.

    Default:
        "/"

    Example:
        >>> context.cmd_prefix = "!"
        >>> # Now commands must start with "!" instead of "/"
    """

    control_no_help_keeps_help: bool = True
    """Controls whether the built-in help command remains available.

    When set to ``True``, the help command will always be available, even if no help text
    is defined for commands. When set to ``False``, the help command can be overridden
    or hidden.

    Default:
        True

    See Also:
        - ``command_action``: For overriding the help command when this is ``False``
    """

    command_action: dict[str, Callable[..., Any]] = field(default_factory=dict)
    """Maps command names to their executable action functions.

    This dictionary defines the behavior of each command. Each key is a command name
    (as defined in your grammar files), and each value is a callable that will be
    executed when that command is invoked.

    Behavior:
        - **Empty mapping**: Commands will load and parse successfully, but executing
          them will have no effect.
        - **Mismatched names**: If a command action name doesn't match any defined
          command, the action is silently ignored. Conversely, if a command has no
          matching action, it will load but do nothing when executed.
        - **Built-in commands**: Cannot be overridden except for ``help``.

    Overriding the help command:
        To override the built-in ``help`` command, you must:

        1. Set ``control_no_help_keeps_help = False``
        2. Provide your own ``"help"`` entry in this dictionary

        Other built-in commands are protected and cannot be overridden.

    Default:
        {} (empty dictionary)

    Example:
        >>> context.command_action = {
        ...     "gamemode": lambda mode, target: set_gamemode(mode, target),
        ...     "tell": lambda player, message: send_message(player, message),
        ...     "say": lambda text: broadcast(text),
        ... }

    Warning:
        Ensure command names in this dictionary exactly match those defined in your
        grammar files. Name mismatches will cause commands to silently fail at runtime.

    Note:
        From the fixtures example: if your grammar defines a command named ``"say"``
        but you provide an action named ``"saying"``, the ``"saying"`` action will be
        ignored, and the ``"say"`` command will load but have no effect when executed.
    """

    command_args_ctrl: dict[str, Any] = field(default_factory=dict)
    """Optional command argument overrides used by the control layer.

    The preferred shape is ``{"command": {"argument": value}}``.  Keeping
    this on the shared context preserves the small existing configuration
    surface; :class:`cmd_router.lib.control._DeeperLevelContext` exposes the
    same mapping for callers that need runtime control.
    """


paths: Final[_Paths] = _Paths()
error: Final[type[_ErrorCodes]] = _ErrorCodes
ctx: Final[_Context] = _Context()
