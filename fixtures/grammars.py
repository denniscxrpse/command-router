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

A graph-shaped example is available through `build_redirect_grammar`.  It
keeps the ``say``/``tell`` base, adds a ``msg`` alias for ``tell``, and adds
an ``execute`` modifier chain of the form
``execute (as <executor> | at <location>)* run <command>``.  Repetition loops
back to ``execute`` and ``run`` forwards to the dispatcher root, so the same
``redirect`` primitive expresses both aliases and repetition.  The data formats
stay tree-only on purpose: redirects need object identity, which is natural in
Python but awkward in TOML/JSON5.
"""

__all__ = ("build_grammar", "build_redirect_grammar")

from collections.abc import Callable, Mapping
from typing import Any

from pkg.lib.commands import CmdType
from pkg.lib.commands.dispatcher import CommandDispatcher
from pkg.sdk import NodeBuilder, argument, literal
from pkg.sdk import build_dispatcher as sdk_build_dispatcher

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


def build_redirect_grammar(actions: Mapping[str, _Action]) -> CommandDispatcher:
    """Return the redirect example built from *actions*.

    The tree contains the ``say``/``tell`` base plus two redirect uses:

    ``msg <target> <message...>``
        Alias for ``tell``. ``msg`` holds no children of its own and redirects
        to the ``tell`` branch, so ``msg Alex hi`` parses with the ``tell``
        handler and ``{"target": "Alex", "message": "hi"}``.

    ``execute (as <executor> | at <location>)* run <command>``
        Repeating modifier chain. Each modifier argument redirects back to the
        ``execute`` branch, so ``as``/``at`` pairs chain without duplicating
        tree levels. ``run`` redirects to the dispatcher root, so ``<command>``
        is any root command such as ``say`` or ``tell``. Modifier arguments
        merge with the subcommand arguments; repeating the same modifier keeps
        the last value (``execute as A as B run say hi`` yields
        ``executor="B"``), while ``as``/``at`` use distinct names precisely so
        ``execute as Steve at home run tell Alex hi`` keeps ``executor``,
        ``location``, ``target``, and ``message`` together.

    Only ``say``/``tell`` handlers are read from *actions*; ``msg`` and
    ``execute`` delegate to the subcommand handler and need no extra entries.
    Children are always tried before a redirect, so direct branches win and a
    redirect acts as a fallback continuation without consuming a token.
    Termination is well-defined: ``set_redirect`` rejects self-targets,
    greedy sources, and redirect-only cycles at build time, while the
    dispatcher tracks ``(node, token-index)`` pairs so a redirect-only loop
    without token progress ends as a structured parse error instead of
    hanging. ``run`` is wired after ``build_dispatcher`` because the root it
    forwards to is created by that call.
    """
    say = literal("say").then(argument("message", CmdType.greedy_string()).executes(actions["say"]))
    tell = literal("tell").then(
        argument("target", CmdType.word()).then(argument("message", CmdType.greedy_string()).executes(actions["tell"]))
    )
    msg = literal("msg").redirect(tell)
    execute, run = _build_execute_tree()
    dispatcher = sdk_build_dispatcher(say, tell, msg, execute)
    run.redirect(dispatcher.root)
    return dispatcher


def _build_execute_tree() -> tuple[NodeBuilder, NodeBuilder]:
    """Build the ``execute`` modifier chain and return ``(execute, run)``.

    ``executor``/``location`` redirect back to ``execute`` for repetition;
    ``run`` is returned unwired so the caller can forward it to the dispatcher
    root once that root exists. The incomplete expectations fall out of those
    edges: ``execute`` suggests ``as``/``at``/``run``, a finished modifier
    suggests the same trio again via its redirect, and a finished ``run``
    suggests the root commands via the root redirect.
    """
    execute = literal("execute")
    executor = argument("executor", CmdType.word()).redirect(execute)
    location = argument("location", CmdType.word()).redirect(execute)
    run: NodeBuilder = literal("run")
    execute.then(
        literal("as").then(executor),
        literal("at").then(location),
        run,
    )
    return execute, run
