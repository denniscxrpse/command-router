#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from dataclasses import dataclass
from typing import Final, final


@dataclass(frozen=True)
class _BaseErr:
    name: str
    message: str
    expected: str | None = None


Error: Final[type[_BaseErr]] = _BaseErr


# fmt: off
@final
class Abort(_BaseErr): ...
@final
class Success(_BaseErr): ...
@final
class DefaultGrammarError(_BaseErr): ...
@final
class GrammarLoadError(_BaseErr): ...
@final
class InvalidGrammarError(_BaseErr): ...
@final
class UnsupportedGrammarFormatError(_BaseErr): ...
@final
class TokenizeInvalidError(_BaseErr): ...
@final
class TokenizeUnsupportedTypeError(_BaseErr): ...
@final
class ControlNotInitializedError(_BaseErr): ...
@final
class ControlFixtureError(_BaseErr): ...
@final
class ControlGrammarError(_BaseErr): ...
@final
class ControlActionError(_BaseErr): ...
@final
class Interrupted(_BaseErr): ...
@final
class ArgumentParseError(_BaseErr): ...
@final
class FixtureInitializationError(_BaseErr):
    """Raised when a fixture's lifecycle flags disagree with the expected state.

    The control layer turns this exception into a structured
    ``ControlInitialization`` failure so callers receive a single, consistent
    result type for both grammar and fixture problems.  Raising it from the
    ``fittings`` module keeps the rule in one place: any caller, fixture, or
    test that bypasses the expected construction order can surface a single
    diagnostic that names the missing step.
    """
