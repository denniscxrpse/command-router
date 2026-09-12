#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Reference fixture showing the single-class ``FixturesSDK`` style.

Subclass ``FixturesSDK`` once: action methods live next to the settings that bind
them, and ``self.logic`` is the holder those actions close over.  Importing
this module alone creates nothing; the control layer constructs ``Fixtures``
when loading this module or accepts a ``FixturesSDK`` instance passed directly
to ``Control.initialize``.

To build your own fixture, copy this shape into your module: add state and
action methods, then map grammar command names to them in ``__init__`` via
``self.logic``.  Command grammar files stay separate under ``fixtures/``;
this module supplies behavior and setup only.
"""

__all__ = ("Fixtures",)

from typing import Any, final

from cmd_router.sdk import FixturesSDK


@final
class Fixtures(FixturesSDK):
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
