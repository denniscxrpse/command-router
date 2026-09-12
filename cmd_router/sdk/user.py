#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

#  The Clear BSD License
#
"""User-facing fixture base and its ready-made default instance.

Subclass :class:`FixturesSDK` to define one fixture in one class.  Action
methods live next to the settings that bind them:

.. code-block:: python

    from cmd_router.sdk import FixturesSDK


    class MyFixtures(FixturesSDK):
        def __init__(self):
            super().__init__()
            self.cmd_prefix = "/"
            self.command_action = {"say": self.say}

        def say(self, message):
            return {"message": message}

Pass an instance directly to ``Control.initialize`` (no fixture module file
needed):

.. code-block:: python

    sdk = MyFixtures()
    control.initialize({"say": "<message...>"}, fixture=sdk)
    control.execute("/say hello")

    Fixtures: A ``FixturesSDK`` with sane defaults (prefix ``"/"``,
    built-in help on, empty actions/overrides, five suggestions).  Import it
    for read-only defaults, quick experiments, or as a base to copy;
    subclass ``FixturesSDK`` for real behavior.
"""

from typing import Any, Final, final

from cmd_router.utils import log

from .backend.holder import FixturesContextHolder
from .backend.settings import FixtureInitializationError
from .backend.setup import FixturesSetup

__all__ = ("Fixtures", "FixturesSDK")


class FixturesSDK(FixturesContextHolder, FixturesSetup):
    """Single-class fixture combining holder state with fixture settings.

    Inherits action-state behavior (``calls``, ``_record``, ``current``)
    and all validated settings (prefix, help, actions, overrides,
    suggestion budgets).  ``logic`` is the instance itself unless ``Control``
    bound a holder first, so a subclass binds actions through ``self.logic``
    and both paths stay correct.

    ``ContextHolder``, ``Setup``, and ``Err`` aliases preserve the legacy
    two-class names for code that still builds holder/setup pairs or catches
    the init error explicitly.
    """

    ContextHolder = FixturesContextHolder
    """Alias preserving the legacy holder base for two-class fixtures."""

    Setup = FixturesSetup
    """Alias preserving the legacy setup base for two-class fixtures."""

    @final
    class Err:
        """Legacy error namespace."""

        InitError: Final[type[FixtureInitializationError]] = FixtureInitializationError
        """(Alias) Raised when a fixture's lifecycle flags disagree with the expected state."""

    def __init__(self, logic: Any = None) -> None:
        """Create holder state and settings for one fixture surface.

        When ``Control`` loads a module whose ``SetupFixtures`` is a
        ``FixturesSDK`` subclass, it binds the fresh holder to the class
        before constructing the setup; that binding wins so actions close
        over the holder.  Otherwise ``logic`` defaults to the instance
        itself, so ``self`` and ``self.logic`` stay interchangeable.
        """
        FixturesContextHolder.__init__(self)
        if logic is None:
            logic = self.logic
            if logic is None:
                logic = self
        FixturesSetup.__init__(self, logic=logic)
        log.debug("user sdk initialized (%s)", type(self).__name__)


Fixtures: Final[FixturesSDK] = FixturesSDK()
"""Ready-made fixture with sane defaults.

Prefix ``"/"``, built-in help enabled, no actions or overrides, and five
suggestions.  Use directly for defaults-only surfaces or subclass
``FixturesSDK`` to add behavior.
"""
