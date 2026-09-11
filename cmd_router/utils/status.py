#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "Status",
    "IStatus",
    "stat",
)

from dataclasses import dataclass
from typing import Final, final


@dataclass(frozen=True)
class _StatusContract:
    _MESSAGE: str | None = None
    _EXPECTED: str | None = None
    _code: int = 255

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        """Return the name of this status type."""
        return self.__class__.__name__

    @property
    def code(self) -> int:
        """Return the exit code for this status.

        Only special statuses may have a meaningful code; by default, all
        statuses are considered a "failure" and return ``255``.

        In general, this property is useless outside the main entrypoint;
        since the command router uses the ``name`` to determine status, it
        makes no sense to return a code that is not a valid status name.

        By consequence, the ``code`` property is unreadable.
        """
        for mro in type(self).__mro__:
            if "_code" in mro.__dict__:
                return mro.__dict__["_code"]
        return -1

    @property
    def message(self) -> str:
        """Return the message for this status."""
        return self._MESSAGE if self._MESSAGE is not None else self.name

    @property
    def expected(self) -> str:
        """Return the expected state for this status."""
        return self._EXPECTED if self._EXPECTED is not None else ""


Status = _StatusContract
IStatus: Final[type[Status]] = _StatusContract


# fmt: off
@final
class _StatusNS:
    """Status namespace for the ``cmd_router`` package."""
    @final
    class Success(IStatus):
        _code=0;...
    @final
    class Abort(IStatus):
        _code=6;...
    @final
    class Interrupted(IStatus):
        _code=2;...
    @final
    class ImpossibleControlState(IStatus):
        """Raised when the unreachable control layer is somehow reached."""
    @final
    class DefaultGrammarError(IStatus): ...
    @final
    class GrammarLoadError(IStatus): ...
    @final
    class InvalidGrammarError(IStatus): ...
    @final
    class UnsupportedGrammarFormatError(IStatus): ...
    @final
    class TokenizeInvalidError(IStatus): ...
    @final
    class TokenizeUnsupportedTypeError(IStatus): ...
    @final
    class ControlNotInitializedError(IStatus): ...
    @final
    class ControlFixtureError(IStatus): ...
    @final
    class ControlGrammarError(IStatus): ...
    @final
    class ControlActionError(IStatus): ...
    @final
    class ArgumentParseError(IStatus): ...
    @final
    class FixtureInitializationError(IStatus):
        """Raised when a fixture's lifecycle flags disagree with the expected state.

        The control layer turns this exception into a structured
        ``ControlInitialization`` failure so callers receive a single, consistent
        result type for both grammar and fixture problems.  Raising it from the
        ``fixtures`` module keeps the rule in one place: any caller, fixture, or
        test that bypasses the expected construction order can surface a single
        diagnostic that names the missing step.
        """
    @final
    class SuggestionServerDisabled(IStatus): ...
#fmt: on

stat: Final[_StatusNS] = _StatusNS()
"""Status namespace."""
