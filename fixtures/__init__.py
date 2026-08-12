#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""
This file is reserved to hold the fixtures' grammar logic.
"""

from typing import Any, ClassVar, Self

from cmd_router.utils.context import ctx as context


def setup() -> None:
    """Configure command behavior after ``FixtureGrammarLogic`` is created."""
    # noinspection protected-member
    logic = _FixG._current
    if logic is None:
        raise RuntimeError("FixtureGrammarLogic must be initialized before setup()")

    # Sets the command prefix to "/". You can change this to whatever you want.
    context.cmd_prefix = "/"

    # Forces the library to keep help even if no help is specified.
    context.control_no_help_keeps_help = True

    # Sets the command actions.
    context.command_action = {
        "gamemode": logic.foo,
        "tell": logic.foo,
        "advancement": logic.bar,
        "say": logic.bar,
    }


class _FixG:
    """Example stateful fixture logic.

    The control layer creates this class exactly once and then calls: `setup`. Put fixture state and setup-time
    work in ``__init__``; importing this module should not execute command logic.
    """

    _current: ClassVar[Self | None] = None

    def __init__(self) -> None:
        type(self)._current = self
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def foo(self, **arguments: Any) -> dict[str, Any]:
        return self._record("foo", arguments)

    def bar(self, **arguments: Any) -> dict[str, Any]:
        return self._record("bar", arguments)

    def _record(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        recorded = dict(arguments)
        self.calls.append((name, recorded))
        if recorded:
            print(*recorded.values())
        return recorded


FixtureGrammarLogic = _FixG
