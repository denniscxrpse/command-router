#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""State holder owned by one fixture initialization.

A fixture module supplies a ``context_holder`` class derived from
``FixturesContextHolder``.  The control layer creates exactly one instance
per initialization attempt and keeps it as ``deeper_level.fixture_logic``.
Importing a fixture module must not create state or run actions; only
calling ``context_holder()`` does.

The base initializer registers the instance as current (both on the concrete
subclass and on this base), creates ``calls`` as a list of
``(action_name, arguments)`` pairs, and flips the holder lifecycle flag in
``_FixtureInnerContext``.  Subclasses add their own fields and action methods
on top; the bundled example uses ``_record`` to make executions easy to
inspect, but production holders may manage to state however they wish.

Configuration (prefix, help policy, actions, overrides, suggestion budgets)
does not live here.  It lives on the ``FixtureSettings`` parent consumed by
``FixturesSetup`` and ``FixturesAPI``.  This holder only owns the runtime state,
and the callables a setup binds' into ``command_action``.
"""

from typing import Any, ClassVar, Self

from cmd_router.utils import log

from .settings import *

__all__ = ("FixturesContextHolder",)


class FixturesContextHolder:
    """Own the state and action methods for one fixture initialization.

    A subclass must call ``super().__init__()`` so the current-holder slots,
    the ``calls`` history, and the lifecycle flag are initialized.  Action
    methods decide which names and value shapes are meaningful; ``_record``
    only copies, stores, and returns the mapping it is given.
    """

    _current: ClassVar[Self | None] = None

    def __init__(self) -> None:
        """Register this holder as current and initialize its call history."""
        type(self)._current = self
        FixturesContextHolder._current = self
        self.calls: list[tuple[str, dict[str, Any]]] = []
        log.info("context holder initialized (%s)", type(self).__name__)
        _FixtureInnerContext.did_context_holder_ever_initialize = True  # ty: ignore[invalid-assignment]

    @classmethod
    def current(cls) -> Self | None:
        """Return the most recently created holder for *cls*, if available."""
        return cls._current

    def _record(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Record and return a copy of one action's keyword arguments.

        The copy keeps the later mutation by the caller from rewriting the
        recorded event.  Captured values are logged at debug level when
        present.
        """
        recorded = dict(arguments)
        self.calls.append((name, recorded))
        log.debug("recorded action %r with %d argument(s)", name, len(recorded))
        if recorded:
            log.debug("captured values:", *recorded.values())
        return recorded
