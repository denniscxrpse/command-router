from cmd_router.lib.control import FixturesContextHolder, FixturesSetup
from dataclasses import dataclass
from typing import Final

__all__ = ["Fixtures"]

@dataclass(frozen=True)
class Fixtures:
    ContextHolder: Final[type[FixturesContextHolder]] = ...
    Setup: Final[type[FixturesSetup]] = ...
