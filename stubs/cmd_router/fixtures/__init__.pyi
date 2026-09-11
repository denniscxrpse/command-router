from dataclasses import dataclass
from typing import Final

from cmd_router.lib.control import *

__all__ = ["Fixtures"]

@dataclass(frozen=True)
class Fixtures:
    ContextHolder: Final[type[FixturesContextHolder]] = ...
    Setup: Final[type[FixturesSetup]] = ...
    @dataclass(frozen=True)
    class Err:
        InitError: Final[type[FixtureInitializationError]] = ...

    def __init__(self, ContextHolder=..., Setup=...) -> None: ...
    def __replace__(self, *, ContextHolder=..., Setup=...) -> None: ...
