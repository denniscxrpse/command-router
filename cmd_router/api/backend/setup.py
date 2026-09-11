#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Fixture setup: settings plus the per-initialization logic binding.

``FixturesSetup`` is the configuration object the control layer compiles
against.  It inherits all validated settings (prefix, help policy, action
mapping, argument overrides, suggestion budgets) from ``FixtureSettings`` and
adds exactly one concern: which holder instance (``logic``) the configured
actions close over.

The lifecycle for module fixtures is:

1. Import the fixture module without running actions.
2. Call ``context_holder()`` to create the holder for this attempt.
3. Bind that holder to ``SetupFixtures.logic`` and call ``SetupFixtures()``.
   The base ``__init__`` validates the binding and creates independent
   defaults via ``FixtureSettings``.
4. The control layer stores module/holder/setup in its deeper state and
   compiles grammars against the setup.

Each ``Control`` gets an independent setup; loading a fixture replaces only
that control's setup.  Action lookup stays late-bound through the mapping,
so replacing ``command_action`` after compilation changes the next
invocation without rebuilding the dispatcher.

Direct users may pass ``logic=...`` explicitly instead of relying on the
class-level binding installed by ``Control``.  ``FixturesAPI`` (in
``cmd_router.api``) builds on this class so a single subclass can own both
holder state and settings with ``logic`` defaulting to itself.
"""

from typing import Any, ClassVar

from cmd_router.utils import flags, log, uctx

from .holder import *
from .settings import *

__all__ = ("FixturesSetup",)


class FixturesSetup(FixtureSettings):
    """Own the command configuration for one fixture initialization.

    ``Control`` binds the newly created holder to the ``logic`` class
    attribute before constructing the setup subclass.  A subclass must call
    ``super().__init__()`` so the binding is checked and independent defaults
    are installed.  The constructor also accepts ``logic`` directly for
    callers creating a setup outside the fixture loader.

    Typical subclass:

    .. code-block:: python

        class SetupFixtures(FixturesSetup):
            def __init__(self):
                super().__init__()
                self.cmd_prefix = "/"
                self.command_action = {"say": self.logic.say}
    """

    logic: Any = None
    """Injection point refreshed for every fixture initialization.

    ``Control`` assigns the fresh holder here before constructing the setup.
    Direct construction may pass ``logic=...`` instead, or rely on the most
    recently created holder as a manual-construction fallback.
    """

    _active_suggestions_size: ClassVar[int | None] = None
    """Last configured suggestions size across setups; read by parse errors.

    ``ParseError._get_suggestions`` has no control reference, so it resolves
    its limit through :meth:`_resolve_suggestions_limit`, which prefers this
    shared value.  The most recently constructed or mutated setup wins,
    mirroring how ``FixturesContextHolder._current`` tracks the latest
    holder.  Kept on this class (not the settings parent) so legacy
    ``monkeypatch.setattr(FixturesSetup, ...)`` isolation keeps working.
    """

    def __init__(self, logic: Any = None) -> None:
        """Bind fixture logic and initialize independent default settings.

        :raises SyntaxError: If no holder was ever created and no logic is
            available (likely a missing ``super().__init__()`` in the holder).
        :raises RuntimeError: If no fixture logic can be associated.
        """
        log.debug("constructing setup (%s)", type(self).__name__)
        if logic is not None:
            self.logic = logic
        if self.logic is None:
            self.logic = FixturesContextHolder.current()
        if self.logic is None:
            # ty: ignore[redundant-condition]
            if not _FixtureInnerContext.did_fixture_setup_ever_initialize:
                raise SyntaxError(
                    "FixtureContextHolder wasn't initialized before FixturesSetup; "
                    "did you forget to call super().__init__()?"
                )
            raise RuntimeError(
                "FixturesSetup.logic must be initialized before construction; "
                "create a context_holder first or let Control initialize the fixture."
            )
        super().__init__()
        FixturesSetup._active_suggestions_size = self._suggestions_size
        log.debug("setup defaults initialized for logic=%s", type(self.logic).__name__)
        _FixtureInnerContext.did_fixture_setup_ever_initialize = True  # ty: ignore[invalid-assignment]

    @classmethod
    def _resolve_suggestions_limit(cls) -> int:
        """Return the suggestions limit active parse errors should enforce.

        When ``flags.max_sized_suggestions`` is enabled the limit is always
        ``uctx.SUGGESTIONS_MAX``; the per-setup value is ignored.  Otherwise
        the most recently configured ``_suggestions_size`` wins, falling back
        to ``5`` when no setup has been constructed yet.  Negative values are
        clamped to ``0`` so slicing never wraps around.
        """
        if flags.max_sized_suggestions:
            return uctx.SUGGESTIONS_MAX
        active = cls._active_suggestions_size
        if isinstance(active, int):
            return max(0, active)
        return 5

    @property
    def suggestions_set_current_size(self) -> int:
        """(Alias) Return how many suggestions a parse error should expose."""
        return self.suggestions_get_size

    @suggestions_set_current_size.setter
    def suggestions_set_current_size(self, v: int) -> None:
        """Set the shared hint budget and publish it for parse errors.

        Validation and the ``max_sized_suggestions`` early-out match
        ``FixtureSettings``; on success the shared
        ``_active_suggestions_size`` is updated so the next
        ``ParseError._get_suggestions`` sees the new limit.
        """
        if flags.max_sized_suggestions:
            log.warning("max_sized_suggestions is enabled; suggestions_set_current_size is ignored.")
            return
        FixtureSettings.suggestions_set_current_size.fset(self, v)
        FixturesSetup._active_suggestions_size = self._suggestions_size
