#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Shared fixture configuration owned by one control surface.

This module is the parent layer for every fixture-owned setting.  It exists
as ``cmd_prefix``, ``lazy_init_help``, ``command_action``,
``command_args_ctrl``, and the suggestion budgets live in exactly one place
instead of being duplicated across ``FixturesSetup`` and
``ControlDeeperContext``.

The layering is:

- ``FixtureSettings`` owns validated per-instance storage and sane defaults.
  Peers (holder, setup, deeper state) read through it; children (user
  ``FixturesAPI`` subclasses and legacy ``SetupFixtures`` subclasses) configure
  through ordinary attribute assignment such as
  ``self.cmd_prefix = "/"``.
- ``FixturesSetup`` (in ``setup.py``) adds the ``logic`` injection point on
  top of these settings plus the shared suggestion-limit global that
  ``ParseError`` resolves without a control reference.
- ``ControlDeeperContext`` keeps delegating to the active setup instead of
  owning a second copy, so there is still exactly one live value per
  control surface.

Lifecycle flags (``_FixtureInnerContext``) also live here, so both the holder
and the setup can flip their own flag without importing each other.  The
control layer resets both flags before constructing a module fixture and
validates them afterward; direct ``FixturesAPI``/``FixturesSetup``
construction bypasses that check because a successful ``__init__`` already
proves the binding.

``FixtureInitializationError`` is the single diagnostic for a skipped
``super().__init__()``.  The control API converts it into a structured
``ControlInitialization`` failure.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cmd_router.suggestions.context import *
from cmd_router.utils import Status, flags, log, stat, uctx

__all__ = ("FixtureInitializationError", "FixtureSettings", "_FixtureInnerContext")

_Action = Callable[..., Any]
_default_pfx = "/"


FixtureInitializationError = stat.FixtureInitializationError
"""Raised when a fixture's lifecycle flags disagree with the expected state.

The control layer turns this exception into a structured
``ControlInitialization`` failure so callers receive a single, consistent
result type for both grammar and fixture problems.
"""


@dataclass(slots=True)
class _FixtureInnerContext:
    did_context_holder_ever_initialize: bool = False
    did_fixture_setup_ever_initialize: bool = False

    @staticmethod
    def reset() -> None:
        """Clear the lifecycle flags before a new fixture is constructed.

        The flags are global, so a stale ``True`` from an earlier setup or
        holder (e.g., the default ``FixturesSetup`` every control surface
        owns) would otherwise mask a fixture that did not call
        ``super().__init__``.  Resetting them at the start of fixture
        construction makes the subsequent ``validate()`` answer the right
        question: "did *this* fixture's components actually finish
        initializing?"
        """
        _FixtureInnerContext.did_context_holder_ever_initialize = False  # ty: ignore[invalid-assignment]
        _FixtureInnerContext.did_fixture_setup_ever_initialize = False  # ty: ignore[invalid-assignment]

    @staticmethod
    def validate() -> None | Status:
        """Return an error when a lifecycle flag reports a missing init.

        Each flag flips to ``True`` only after the corresponding ``__init__``
        completes.  Callers should call ``reset()`` before constructing the
        holder and setup, so a stale flag from a previous fixture or the
        default control setup does not mask an unfinished fixture.
        """
        fic = _FixtureInnerContext
        # ty: ignore[redundant-condition]
        if not (fic.did_context_holder_ever_initialize, fic.did_fixture_setup_ever_initialize):
            log.critical("very rare error! is the fixture lifecycle order correct? are we somehow racing?")
        # ty: ignore[redundant-condition]
        if not fic.did_context_holder_ever_initialize:
            return FixtureInitializationError(
                "FixturesContextHolder did not finish initialization; "
                "the context_holder factory must call super().__init__() before returning."
            )
        # ty: ignore[redundant-condition]
        if not fic.did_fixture_setup_ever_initialize:
            return FixtureInitializationError(
                "FixturesSetup did not finish initialization; "
                "the SetupFixtures class must call super().__init__() and finish construction."
            )
        return None


class FixtureSettings:
    """Own validated fixture settings with per-instance defaults.

    Storage is always per instance, never shared between controls.  The
    shared suggestion-limit global lives on ``FixturesSetup`` (see
    ``setup.py``) so legacy ``monkeypatch.setattr(FixturesSetup, ...)``
    isolation keeps working; this parent only owns the instance value and
    validation.  ``FixturesSetup`` overrides the suggestions' setter and
    ``__init__`` to publish to that shared global.

    Subclasses configure through normal assignment in ``__init__`` after
    calling ``super().__init__()``:

    .. code-block:: python

        class SetupFixtures(FixturesSetup):
            def __init__(self):
                super().__init__()
                self.cmd_prefix = "/"
                self.command_action = {"say": self.logic.say}

    Subclasses may also override a property when a value must be computed
    dynamically, but they must still call the base initializer so the
    remaining settings keep their defaults.
    """

    def __init__(self) -> None:
        """Initialize independent default settings for one fixture surface."""
        self._cmd_prefix = _default_pfx
        self._lazy_init_help = True
        self._command_action: dict[str, _Action] = {}
        self._command_args_ctrl: dict[str, Any] = {}
        self._suggestions_size: int = 5 if not flags.max_sized_suggestions else uctx.SUGGESTIONS_MAX
        log.debug("fixture settings defaults initialized")

    @staticmethod
    def __typerror__(name: str, value: Any, expected: type[Any]) -> TypeError:
        """Build the type error for an invalid assignment to a setting.

        ``name`` is deliberately an explicit property name rather than a value
        read from that property.  Values do not retain the attribute name that
        produced them, and inferring a name from a value would be both
        ambiguous and wrong for repeated defaults.
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
        """Set the command prefix, rejecting non-string configuration.

        Any input that does not start with this prefix is treated as ordinary
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
    def lazy_init_help(self) -> bool:
        """Return whether the compiler should install its built-in help command."""
        return self._lazy_init_help

    @lazy_init_help.setter
    def lazy_init_help(self, v: bool) -> None:
        """Control whether the built-in help command remains available.

        When ``True``, the help command is always available.  When ``False``,
        it can be overridden or hidden.
        """
        if not isinstance(v, bool):
            raise self.__typerror__("lazy_init_help", v, bool)
        self._lazy_init_help = v
        log.debug("built-in help policy set to %s", v)

    @property
    def command_action(self) -> dict[str, _Action]:
        """Return the live command-name-to-action mapping."""
        return self._command_action

    @command_action.setter
    def command_action(self, v: dict[str, _Action]) -> None:
        """Map grammar command names to their executable action callables.

        Each key is a command name from the grammar files; each value runs
        when that command is invoked.  Replacing the dict replaces the
        reference; mutating it in place is also visible because compiled
        handlers look actions up late.
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

        The preferred shape is ``{"command": {"argument": value}}``.  Runtime
        callers normally change this through
        ``deeper_level.set_command_args`` rather than during fixture setup.
        """
        if not isinstance(v, dict):
            raise self.__typerror__("command_args_ctrl", v, dict)
        self._command_args_ctrl = v
        log.debug("argument overrides set (%d command(s))", len(v))

    @property
    def suggestions_max_list_size(self) -> int:
        """Return the maximum number of suggestions the library will emit.

        This is always ``uctx.SUGGESTIONS_MAX``.  It bounds
        ``suggestions_set_current_size`` and the worst-case work of suggestion
        ranking.
        """
        return uctx.SUGGESTIONS_MAX

    @property
    def suggestions_get_size(self) -> int:
        """Return how many suggestions a parse error should expose.

        Children configure this through ``suggestions_set_current_size``.  For
        example, ``2`` exposes the first two ``expected`` candidates.  When
        ``flags.max_sized_suggestions`` is enabled the effective limit is
        always ``SUGGESTIONS_MAX`` regardless of this stored value.
        """
        return self._suggestions_size

    @property
    def suggestions_set_current_size(self) -> int:
        """(Alias) Return how many suggestions a parse error should expose."""
        return self.suggestions_get_size

    @suggestions_set_current_size.setter
    def suggestions_set_current_size(self, v: int) -> None:
        """Set how many suggestions a parse error should expose.

        The value truncates ``ParseError.expected`` to its first ``v``
        entries.  Ignored while ``flags.max_sized_suggestions`` is enabled.
        ``FixturesSetup`` overrides this to also publish to the shared
        global that parse errors resolve; bare settings only store the
        instance value.

        :raises TypeError: If *v* is not an ``int``.
        :raises ValueError: If *v* is negative or larger than ``SUGGESTIONS_MAX``.
        """
        if flags.max_sized_suggestions:
            log.warning("max_sized_suggestions is enabled; suggestions_set_current_size is ignored.")
            return
        if not isinstance(v, int):
            raise self.__typerror__("suggestions_max_list_size", v, int)
        if v < 0:
            raise ValueError("suggestions_max_list_size must be >= 0")
        if v > uctx.SUGGESTIONS_MAX:
            raise ValueError(f"suggestions_max_list_size must be <= {uctx.SUGGESTIONS_MAX}")
        self._suggestions_size = v

    @property
    def suggestions_server_address(self) -> str:
        """Return the address of the suggestions server."""
        return lazy_suggest_srv_ctx.address

    @suggestions_server_address.setter
    def suggestions_server_address(self, v: str) -> None:
        """Set the address of the suggestions server."""
        lazy_suggest_srv_ctx.address = v

    @property
    def suggestions_server_port(self) -> int:
        """Return the port of the suggestions server."""
        return lazy_suggest_srv_ctx.port

    @suggestions_server_port.setter
    def suggestions_server_port(self, v: int) -> None:
        """Set the port of the suggestions server."""
        lazy_suggest_srv_ctx.port = v
