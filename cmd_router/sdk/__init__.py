#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Pleasant registration and fixture defaults for command surfaces.

Use the builder for trees and :class:`FixturesSDK` for behavior:

.. code-block:: python

    from cmd_router.sdk import FixturesSDK, argument, build_dispatcher, literal
    from cmd_router.lib.commands import CmdType


    class MyFixtures(FixturesSDK):
        def __init__(self):
            super().__init__()
            self.command_action = {"say": self.say}

        def say(self, message):
            return {"message": message}


    sdk = MyFixtures()
    dispatcher = build_dispatcher(
        literal("say").then(
            argument("message", CmdType.greedy_string()).executes(sdk.say)
        )
    )

Fixtures: Default :class:`FixturesSDK` instance (prefix ``"/"``, help on,
empty actions).  Subclass :class:`FixturesSDK` for real apps.

`literal` / `argument`: Start builder branches; chain with ``.then(...)``
for nesting/choices and ``.executes(...)`` for handlers.
Builders only call ``add_child``/``set_command``, so they parse exactly
like hand-built trees.

`cmd_router.sdk.backend`: Advanced peers (settings, holder, setup,
builder, loader) for custom control integration, mirroring how
``control.deeper`` exposes the live state.
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
    "FixturesSDK",
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
from .user import Fixtures, FixturesSDK
