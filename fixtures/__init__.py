#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Reference fixture showing the single-class ``FixturesAPI`` style.

Subclass ``FixturesAPI`` once: action methods live next to the settings that bind
them, and ``self.logic`` is the holder those actions close over.  Importing
this module alone creates nothing; the control layer constructs the class
(either as a ``context_holder``/``SetupFixtures`` module fixture or, more
simply, from a ``FixturesAPI`` instance passed directly to
``Control.initialize``).

To build your own fixture, copy this shape into your module: add state and
action methods, then map grammar command names to them in ``__init__`` via
``self.logic``.  Command grammar files stay separate under ``fixtures/``;
this module supplies behavior and setup only.

``context_holder`` and ``SetupFixtures`` below are loader-contract aliases
for the one class, so file-based loading keeps working.  They are not
separate extension points.
"""

__all__ = ("Fixtures", "SetupFixtures", "context_holder")

from typing import Any, final

from cmd_router.api import FixturesAPI


@final
class Fixtures(FixturesAPI):
    """Hold the example state, actions, and command configuration."""

    def __init__(self, logic: Any = None) -> None:
        """Build example values using the holder bound to ``logic``."""
        super().__init__(logic=logic)

        # Commands in the example are written as /say, /tell, and so on.
        self.cmd_prefix = "/"

        # Keep the generated /help command unless an application overrides it.
        self.lazy_init_help = True

        # Bind grammar names to methods on this initialization's holder.
        self.command_action = {
            "gamemode": self.logic.foo,
            "tell": self.logic.foo,
            "advancement": self.logic.bar,
            "say": self.logic.bar,
        }

        # How many completion hints a parse error exposes via
        # ``error["suggestions"]`` (first N of ``expected``). The bundled
        # default is 5; setting it to 2 would make consumers see
        # ``{"suggestions": ["word1", "word2"]}`` for a matching failure.
        # Ignored while ``flags.max_sized_suggestions`` forces SUGGESTIONS_MAX.
        self.suggestions_set_current_size = 5

    def foo(self, **arguments: Any) -> dict[str, Any]:
        """Record and return arguments for the ``foo`` action family."""
        return self._record("foo", arguments)

    def bar(self, **arguments: Any) -> dict[str, Any]:
        """Record and return arguments for the ``bar`` action family."""
        return self._record("bar", arguments)


context_holder = Fixtures
"""Loader-contract alias so file-based fixtures resolve the holder."""

SetupFixtures = Fixtures
"""Loader-contract alias so file-based fixtures resolve the setup."""
