#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Configuration and state-holder classes used by control fixtures.

The control API deliberately separates immutable application constants from
fixture-owned runtime configuration.  ``cmd_router.utils.context.uctx`` now
contains only shared constants and schema keys; it is not a settings object and
does not expose command-prefix, help, action, or argument-override setters.
Those values belong to a ``FixturesSetup`` instance.

A fixture module supplies two child classes and one factory alias:

``context_holder``
    A class derived from ``FixturesContextHolder``.  The control layer creates
    exactly one instance for an initialization attempt and keeps it in
    ``deeper_level.fixture_logic``.  The base class registers the instance as
    the current fixture holder and provides the small ``calls``/``_record``
    conveniences used by the example fixture.  Subclasses may add any state
    and action methods they need; importing a fixture must not execute those
    actions.
``SetupFixtures``
    A class derived from ``FixturesSetup``.  The control layer assigns the
    newly created holder to the setup class's ``logic`` attribute before it
    constructs the setup instance.  The subclass calls ``super().__init__``
    and then fills in its configuration, normally with ordinary assignments
    such as ``self.command_action = {...}``.

The lifecycle is therefore:

1. Import the fixture module without running command actions.
2. Call ``context_holder()``.  ``FixturesContextHolder.__init__`` records the
   new state holder as current and initializes its recording list.
3. Bind that holder to ``SetupFixtures.logic`` and call ``SetupFixtures()``.
   ``FixturesSetup.__init__`` validates the binding and creates independent
   default configuration values.
4. Store the resulting setup, module, and holder in the control's deeper
   state.  Grammar compilation reads configuration from the setup object.
5. Execute commands through the dispatcher.  Action lookup remains late-bound
   through the setup's action mapping, while runtime argument overrides remain
   available through ``DeeperLevelContext``.

``FixturesSetup`` is intentionally a small mutable configuration object rather
than a global singleton.  Each ``Control`` gets an independent default setup,
and loading a fixture replaces only that control's setup.  This prevents one
fixture or test from changing another control's prefix, help policy, actions,
or argument overrides.  Properties provide validation while still allowing a
fixture subclass to use the straightforward ``self.<setting> = value`` style;
subclasses may also override the properties when configuration needs to be
computed dynamically.

The four settings are:

``cmd_prefix``
    A string required before a command.  ``Control`` treats input without this prefix
    as ordinary non-command input.  The default is ``"/"``.
``control_no_help_keeps_help``
    A boolean controlling the compiler's generated ``help`` command.  The
    default is ``True``.
``command_action``
    A mapping from grammar command names to callable actions.  It defaults to
    an empty dictionary.  A command can still compile without an action; its
    handler returns ``None`` when invoked.  The compiler rejects a configured
    non-callable value.
``command_args_ctrl``
    A mapping of command names to argument overrides, defaulting to an empty
    dictionary.  It is normally changed through
    ``deeper_level.set_command_args`` rather than during fixture setup.

The setup class's ``logic`` attribute is an injection point, not a global
context.  It is refreshed for every fixture initialization, so action methods
can safely close over the holder created for that control.  Direct users who
construct a setup manually may pass ``logic=...`` to ``FixturesSetup`` or
construct a ``FixturesContextHolder`` first and let the current-holder
fallback supply it.
"""

from collections.abc import Callable
from typing import Any, ClassVar, Self

from cmd_router.utils.logger import log

__all__ = ("FixturesContextHolder", "FixturesSetup")

_Action = Callable[..., Any]
_default_pfx = "/"


class FixturesContextHolder:
    """Base class for the state and action methods owned by one fixture.

    A subclass should call ``super().__init__()`` before or after initializing
    its own fields.  The base initializer stores the instance in both the
    subclass's ``_current`` slot and the base-class current slot, then creates
    ``calls`` as a list of ``(action_name, arguments)`` pairs.  The current
    slot is primarily useful to small fixture setups and compatibility code;
    the control layer passes the same instance explicitly to
    ``FixturesSetup.logic``.

    ``_record`` copies its argument mapping before storing it, prints captured
    values when present, and returns the copy.  It is only a convenience for
    the bundled fixture example; production subclasses may ignore it and
    implement their own state management.
    """

    _current: ClassVar[Self | None] = None

    def __init__(self) -> None:
        """Register this holder as current and initialize its call history."""
        type(self)._current = self
        FixturesContextHolder._current = self
        self.calls: list[tuple[str, dict[str, Any]]] = []
        log.info("context holder initialized (%s)", type(self).__name__)

    @classmethod
    def current(cls) -> Self | None:
        """Return the most recently created holder for *cls*, if available."""
        return cls._current

    def _record(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Record and return a copy of one action's keyword arguments.

        The method intentionally does not validate *name* or *arguments*;
        action methods decide which names and value shapes are meaningful.  A
        copied mapping keeps the later mutation by the caller from rewriting the
        recorded event.
        """
        recorded = dict(arguments)
        self.calls.append((name, recorded))
        log.debug("recorded action %r with %d argument(s)", name, len(recorded))
        if recorded:
            log.debug("captured values:", *recorded.values())
        return recorded


class FixturesSetup:
    """Own the command configuration associated with one fixture instance.

    ``Control`` binds the newly created context holder to the class attribute
    ``logic`` before constructing a fixture setup subclass.  A subclass must
    call ``super().__init__()`` so the binding is checked and the independent
    setting storage is initialized.  The constructor also accepts ``logic``
    directly for callers creating a setup outside the fixture loader.

    The settings are mutable properties with narrow validation.  Assigning a
    new action dictionary replaces the mapping reference; mutating that
    dictionary in place is also visible to compiled handlers because the action
    lookup is intentionally late-bound.  Defaults are created, per instance,
    never shared between controls.

    Subclasses may use either of these styles:

    .. code-block:: python

        class SetupFixtures(FixturesSetup):
            def __init__(self):
                super().__init__()
                self.cmd_prefix = "/"
                self.control_no_help_keeps_help = True
                self.command_action = {"say": self.logic.say}

    Or they may override a property when a setting should be calculated from
     the fixture state.  In that case the subclass still needs to call the base
    initializer so ``logic`` is validated and the remaining settings have
    their normal defaults.
    """

    logic: Any = None

    def __init__(self, logic: Any = None) -> None:
        """Bind fixture logic and initialize independent default settings.

        If *logic* is supplied, it becomes this setup instance's logic.  When
        it is omitted, the class-level binding installed by ``Control`` is
        used; if that is also absent, the most recently constructed
        ``FixturesContextHolder`` is used as a convenient manual-construction
        fallback.

        :raises RuntimeError: If no fixture logic can be associated with the setup.
        """
        log.debug("constructing setup (%s)", type(self).__name__)
        if logic is not None:
            self.logic = logic
        if self.logic is None:
            self.logic = FixturesContextHolder.current()
        if self.logic is None:
            raise RuntimeError(
                "FixturesSetup.logic must be initialized before construction; "
                "create a context_holder first or let Control initialize the fixture."
            )

        self._cmd_prefix = _default_pfx
        self._control_no_help_keeps_help = True
        self._command_action: dict[str, _Action] = {}
        self._command_args_ctrl: dict[str, Any] = {}
        log.debug("setup defaults initialized for logic=%s", type(self.logic).__name__)

    @staticmethod
    def __typerror__(name: str, value: Any, expected: type[Any]) -> TypeError:
        """Build the type error for an invalid assignment to a setup property.

        *name* is deliberately an explicit property name rather than a value
        read from that property.  Values do not retain the attribute name that
        produced them, and inferring a name from a value would be both
        ambiguous and wrong for repeated defaults. The setter supplies *expected*
        so the diagnostic remains correct even when *value* is a string, a class-like
        object, or another value without ``__name__``.
        """
        actual = type(value).__name__
        log.error("invalid %s value; expected %s, got %s", name, expected.__name__, actual)
        return TypeError(f"{name} must be a {expected.__name__}, got {actual}")

    @property
    def cmd_prefix(self) -> str:
        """Return the command prefix used by the associated control surface."""
        return self._cmd_prefix

    @cmd_prefix.setter
    def cmd_prefix(self, v: str) -> None:
        """
        Set the command prefix, rejecting non-string configuration.
        Any input that does not start with this prefix is treated as greedy
        (non-command) input.
        """
        if v == "":
            log.warning("empty strings are not allowed as command prefixes; using defaults.")
            v = _default_pfx
        if not isinstance(v, str):
            raise self.__typerror__("cmd_prefix", v, str)
        self._cmd_prefix = v
        log.debug("command prefix set to %r", v)

    @property
    def control_no_help_keeps_help(self) -> bool:
        """Return whether the compiler should install its built-in help command."""
        return self._control_no_help_keeps_help

    @control_no_help_keeps_help.setter
    def control_no_help_keeps_help(self, v: bool) -> None:
        """
        Controls whether the built-in help command remains available. When set to ``True``,
        the help command will always be available, even if no help text is defined for
        commands. When set to ``False``, the help command can be overridden
        or hidden.
        """
        if not isinstance(v, bool):
            raise self.__typerror__("control_no_help_keeps_help", v, bool)
        self._control_no_help_keeps_help = v
        log.debug("built-in help policy set to %s", v)

    @property
    def command_action(self) -> dict[str, _Action]:
        """Return the live command-name-to-action mapping."""
        return self._command_action

    @command_action.setter
    def command_action(self, v: dict[str, _Action]) -> None:
        """
        Maps command names to their executable action functions. This dictionary
        defines the behavior of each command. Each key is a command name (as defined
        in your grammar files), and each value is a callable that will be executed
        when that command is invoked.
        """
        if not isinstance(v, dict):
            raise self.__typerror__("command_action", v, dict)
        self._command_action = v
        log.debug("command actions set (%d name(s))", len(v))

    @property
    def command_args_ctrl(self) -> dict[str, Any]:
        """Return the live mapping of command argument overrides."""
        return self._command_args_ctrl

    @command_args_ctrl.setter
    def command_args_ctrl(self, v: dict[str, Any]) -> None:
        """Replace argument overrides after validating their container type.
        The preferred shape is ``{"command": {"argument": value}}``.  Keeping
        this on the shared context preserves the small existing configuration
        surface; ``DeeperLevelContext`` exposes the same mapping for callers
        that need runtime control.
        """
        if not isinstance(v, dict):
            raise self.__typerror__("command_args_ctrl", v, dict)
        self._command_args_ctrl = v
        log.debug("argument overrides set (%d command(s))", len(v))
