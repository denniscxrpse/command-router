#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Convenience façade for the selected command-control API.

The API remains available through ``cmd_router.lib.*`` and any other ``*.api.*``
package under ``cmd_router.lib``. This namespace is a direct convenience façade,
not a second implementation: its names refer to the original classes and values.

Prefer explicit imports from this module.  Wildcard imports are discouraged
because callers cannot know which API names are safe to combine, although a
deliberate ``__all__`` is provided for callers that need one.

Choose one API namespace for an application.  Mixing ``cmd_router.api`` with
``cmd_router.lib.control.api``, for example, can combine the public API and
library namespaces in unsafe ways; this package does not add misuse safeguards.

Fixture-backed applications normally import ``FixturesContextHolder`` and
``FixturesSetup`` from here.  Their fixture module should expose a
``context_holder`` alias and a ``SetupFixtures`` child class.  The control
layer creates the holder, assigns it to ``SetupFixtures.logic``, and reads the
setup properties while compiling grammars.  Command settings are no longer
written to the process-wide ``uctx`` object.
"""

# __all__ = ("control", "control_surface", "control_deeper")
#
# from cmd_router.lib.control.api import *
#
# control_surface = surface
# control_deeper = deeper_level
