#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Reference fixture used as an example of the command-router application.

This module is intentionally a small, user-managed example of the fixture API.
It defines the state holder that owns action methods and a separate setup class
that owns command configuration.  The control layer imports the module, calls
``context_holder()`` once, binds that instance to ``SetupFixtures.logic``, and
then constructs ``SetupFixtures()``.  Importing this module alone does not
create state, register actions, or execute commands.

The two public extension points are:

- ``FixturesContextHolder``: Subclass the API base when adding state and command
  methods. Call ``super().__init__()`` so the base class initializes ``calls``
  and records the current holder.  Methods such as ``foo`` and ``bar`` can return
  any application value; this example uses ``_record`` to make executions easy
  to inspect.
- ``SetupFixtures``: Subclass the API setup base when defining configuration. Call
  ``super().__init__()`` first, then assign ``self.cmd_prefix``, ``self.lazy_init_help``,
  ``self.command_action``, or ``self.command_args_ctrl``. ``self.logic`` is the holder
  created for the current control initialization, so actions can be bound directly to
  its methods.

The ``context_holder`` alias is part of the fixture contract.  Its name keeps
the loader independent of the concrete class name and makes replacing this
example with an application-specific holder straightforward.  The
control API likewise discovers the ``SetupFixtures`` class name.

To customize this fixture, add state to ``FixturesContextHolder``, add action
methods to it, and map grammar command names to those methods in
``SetupFixtures.command_action``.  Command grammar files remain separate under
``fixtures/``; this Python module supplies behavior and setup only.
"""

from typing import Any, final

from cmd_router.fittings import Fixtures as _Fixtures

__all__ = ("FixturesContextHolder", "SetupFixtures", "context_holder")


@final
class FixturesContextHolder(_Fixtures.ContextHolder):  # ty: ignore[unsupported-base]
    """Hold the example state and implement the fixture's command actions."""

    def __init__(self) -> None:
        """Initialize the base call history and any fixture-owned state."""
        super().__init__()

    def foo(self, **arguments: Any) -> dict[str, Any]:
        """Record and return arguments for the ``foo`` action family."""
        return self._record("foo", arguments)

    def bar(self, **arguments: Any) -> dict[str, Any]:
        """Record and return arguments for the ``bar`` action family."""
        return self._record("bar", arguments)

    ...


context_holder = FixturesContextHolder


@final
class SetupFixtures(_Fixtures.Setup):  # ty: ignore[unsupported-base]
    """Configure the example prefix, help policy, and grammar actions."""

    def __init__(self) -> None:
        """Build setup values using the holder injected by ``Control``."""
        super().__init__()

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

        ...
