from typing import Any, Final

from .backend.holder import FixturesContextHolder
from .backend.settings import FixtureInitializationError
from .backend.setup import FixturesSetup

__all__ = ["FixturesSDK", "Fixtures"]

class FixturesSDK(FixturesContextHolder, FixturesSetup):
    ContextHolder = FixturesContextHolder
    Setup = FixturesSetup

    class Err:
        InitError: Final[type[FixtureInitializationError]]

    def __init__(self, logic: Any = None) -> None: ...

Fixtures: Final[FixturesSDK]
