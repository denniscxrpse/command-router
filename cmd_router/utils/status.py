#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "IStatus",
    "Status",
    "stat",
)

from dataclasses import dataclass
from typing import Final, final


@dataclass(frozen=True)
class _StatusContract:
    _MESSAGE: str | None = None
    _EXPECTED: str | None = None
    _code: int | None = None

    def __str__(self) -> str:
        return self.name

    @property
    def name(self) -> str:
        """Return the name of this status type."""
        return self.__class__.__name__

    @property
    def code(self) -> int:
        """Return the exit code for this status.

        Only special statuses may have a non-negative code; by default, all
        statuses are considered a "failure" and return a negative code (``-1``).

        In general, this property is useless outside the main entrypoint;
        since the command router uses the ``name`` to determine status, it
        makes no sense to return a code that is not a valid status name.

        By consequence, the ``code`` property is unreadable.
        """
        for klass in type(self).__mro__:
            if "_code" in klass.__dict__:
                value = klass.__dict__["_code"]
                if isinstance(value, int):
                    return value
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
    class Success(_StatusContract):
        _code=0;...
    @final
    class Abort(_StatusContract):
        _code=1;...
    @final
    class Interrupted(_StatusContract):
        _code=2;...
    @final
    class DefaultGrammarError(_StatusContract): ...
    @final
    class GrammarLoadError(_StatusContract): ...
    @final
    class InvalidGrammarError(_StatusContract): ...
    @final
    class UnsupportedGrammarFormatError(_StatusContract): ...
    @final
    class TokenizeInvalidError(_StatusContract): ...
    @final
    class TokenizeUnsupportedTypeError(_StatusContract): ...
    @final
    class ControlNotInitializedError(_StatusContract): ...
    @final
    class ControlFixtureError(_StatusContract): ...
    @final
    class ControlGrammarError(_StatusContract): ...
    @final
    class ControlActionError(_StatusContract): ...
    @final
    class ArgumentParseError(_StatusContract): ...
    @final
    class FixtureInitializationError(_StatusContract):
        """Raised when a fixture's lifecycle flags disagree with the expected state.

        The control layer turns this exception into a structured
        ``ControlInitialization`` failure so callers receive a single, consistent
        result type for both grammar and fixture problems.  Raising it from the
        ``fittings`` module keeps the rule in one place: any caller, fixture, or
        test that bypasses the expected construction order can surface a single
        diagnostic that names the missing step.
        """
#fmt: on

stat: Final[_StatusNS] = _StatusNS()
