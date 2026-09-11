#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Pleasant registration and fixture defaults for command surfaces.

Use the builder for trees and :class:`FixturesAPI` for behavior:

.. code-block:: python

    from cmd_router.api import FixturesAPI, argument, build_dispatcher, literal
    from cmd_router.lib.commands import CmdType

    class MyFixtures(FixturesAPI):
        def __init__(self):
            super().__init__()
            self.command_action = {"say": self.say}

        def say(self, message):
            return {"message": message}

    api = MyFixtures()
    dispatcher = build_dispatcher(
        literal("say").then(
            argument("message", CmdType.greedy_string()).executes(api.say)
        )
    )

Fixtures: Default :class:`FixturesAPI` instance (prefix ``"/"``, help on,
empty actions).  Subclass :class:`FixturesAPI` for real apps.

`literal` / `argument`: Start builder branches; chain with ``.then(...)``
for nesting/choices and ``.executes(...)`` for handlers.
Builders only call ``add_child``/``set_command``, so they parse exactly
like hand-built trees.

`cmd_router.api.backend`: Advanced peers (settings, holder, setup,
builder, loader) for custom control integration, mirroring how
``control.deeper`` exposes live state.
"""

__all__ = (
    "ArgumentBuilder",
    "FixtureInitializationError",
    "FixtureSettings",
    "FixturesContextHolder",
    "FixturesSetup",
    "LiteralBuilder",
    "NodeBuilder",
    "argument",
    "build_dispatcher",
    "literal",
    "load_fixture_module",
    "Fixtures",
    "FixturesAPI",
)

from .backend import (
    ArgumentBuilder,
    FixtureInitializationError,
    FixturesContextHolder,
    FixtureSettings,
    FixturesSetup,
    LiteralBuilder,
    NodeBuilder,
    argument,
    build_dispatcher,
    literal,
    load_fixture_module,
)
from .user import Fixtures, FixturesAPI
