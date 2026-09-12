#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Build the bundled command grammar directly with the SDK.

The TOML and JSON5 files in this directory are the commonly used grammar
format.  They keep command definitions easy to edit, validate, persist, and
load without executing Python.  This module is the advanced alternative: it
initializes the same command surface with the SDK's builder and returns a
``CommandDispatcher``.

The Python form is useful when the grammar needs capabilities the data formats
deliberately avoid.  It can attach handlers while the tree is built, select or
repeat branches from Python data, reuse helper functions for nested command
shapes, and use any ``ArgumentType`` supported by the command tree.  Those
capabilities remove the original grammar files' limits around fixed syntax,
fixed argument types, and data-only command definitions, while preserving the
same dispatcher matching behavior.

The fixture passes its ``command_action`` mapping to `build_grammar`, so
the resulting Python grammar and the TOML/JSON5 grammars execute the same
actions.  Applications can call this function directly when they want an
embedded command tree instead of loading a grammar file.
"""

__all__ = ("build_grammar",)

from collections.abc import Callable, Mapping
from typing import Any

from cmd_router.lib.commands import CmdType
from cmd_router.lib.commands.dispatcher import CommandDispatcher
from cmd_router.sdk import NodeBuilder, argument, literal
from cmd_router.sdk import build_dispatcher as sdk_build_dispatcher

_Action = Callable[..., Any]


def build_grammar(actions: Mapping[str, _Action]) -> CommandDispatcher:
    """Return the bundled command tree built from *actions*.

    The action names match the command keys used by the TOML and JSON5
    fixtures.  Each builder branch is assembled here so callers can use the
    Python grammar independently of the file-backed control initialization.
    """
    return sdk_build_dispatcher(
        literal("say").then(argument("message", CmdType.greedy_string()).executes(actions["say"])),
        literal("tell").then(
            argument("target", CmdType.word()).then(
                argument("message", CmdType.greedy_string()).executes(actions["tell"])
            )
        ),
        _build_gamemode_tree(actions),
        _build_advancement_tree(actions),
    )


def _build_gamemode_tree(actions: Mapping[str, _Action]) -> NodeBuilder:
    """Build gamemode choices with an optional target argument."""
    action = actions["gamemode"]
    return literal("gamemode").then(
        *[
            literal(mode)
            .executes(action)
            .then(
                argument("target", CmdType.word()).executes(action),
            )
            for mode in ("survival", "creative", "adventure", "spectator")
        ]
    )


def _build_advancement_tree(actions: Mapping[str, _Action]) -> NodeBuilder:
    """Build grant/revoke branches with the ``*`` and ``only`` forms."""
    action = actions["advancement"]
    roots: list[NodeBuilder] = []
    for operation in ("grant", "revoke"):
        target = argument("target", CmdType.word())
        target.then(
            literal("*").executes(action),
            literal("only").then(
                argument("advancement", CmdType.word())
                .executes(action)
                .then(argument("criterion", CmdType.word()).executes(action))
            ),
        )
        roots.append(literal(operation).then(target))
    return literal("advancement").then(*roots)
