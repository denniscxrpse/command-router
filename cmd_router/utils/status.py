#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "Status",
    "StatusType",
    "stat",
)

from dataclasses import dataclass
from typing import Final, final


@dataclass(frozen=True)
class _BaseStatus:
    _MESSAGE: str | None = None
    _EXPECTED: str | None = None

    def __str__(self) -> str:
        return self.name

    @property
    def message(self) -> str:
        """Return the message for this status."""
        return self._MESSAGE if self._MESSAGE is not None else self.name

    @property
    def expected(self) -> str:
        """Return the expected state for this status."""
        return self._EXPECTED if self._EXPECTED is not None else ""

    @property
    def name(self) -> str:
        """Return the name of this status type."""
        return self.__class__.__name__


StatusType = _BaseStatus
Status: Final[type[StatusType]] = _BaseStatus


# fmt: off
@final
class _Status:
    """Status namespace for the ``cmd_router`` package."""
    @final
    class Abort(_BaseStatus): ...
    @final
    class Success(_BaseStatus): ...
    @final
    class DefaultGrammarError(_BaseStatus): ...
    @final
    class GrammarLoadError(_BaseStatus): ...
    @final
    class InvalidGrammarError(_BaseStatus): ...
    @final
    class UnsupportedGrammarFormatError(_BaseStatus): ...
    @final
    class TokenizeInvalidError(_BaseStatus): ...
    @final
    class TokenizeUnsupportedTypeError(_BaseStatus): ...
    @final
    class ControlNotInitializedError(_BaseStatus): ...
    @final
    class ControlFixtureError(_BaseStatus): ...
    @final
    class ControlGrammarError(_BaseStatus): ...
    @final
    class ControlActionError(_BaseStatus): ...
    @final
    class Interrupted(_BaseStatus): ...
    @final
    class ArgumentParseError(_BaseStatus): ...
    @final
    class FixtureInitializationError(_BaseStatus):
        """Raised when a fixture's lifecycle flags disagree with the expected state.

        The control layer turns this exception into a structured
        ``ControlInitialization`` failure so callers receive a single, consistent
        result type for both grammar and fixture problems.  Raising it from the
        ``fittings`` module keeps the rule in one place: any caller, fixture, or
        test that bypasses the expected construction order can surface a single
        diagnostic that names the missing step.
        """
#fmt: on

stat: Final[_Status] = _Status()
