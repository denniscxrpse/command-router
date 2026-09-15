from typing import Any, ClassVar

from .holder import *
from .settings import *

__all__ = ["FixturesSetup"]

class FixturesSetup(FixtureSettings):
    logic: Any
    _active_suggestions_size: ClassVar[int | None]
    def __init__(self, logic: Any = None) -> None: ...
    @classmethod
    def _resolve_suggestions_limit(cls) -> int: ...
    @property
    def suggestions_set_current_size(self) -> int: ...
    @suggestions_set_current_size.setter
    def suggestions_set_current_size(self, v: int) -> None: ...
