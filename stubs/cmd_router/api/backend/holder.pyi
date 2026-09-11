from typing import Any, ClassVar, Self

from .settings import *

__all__ = ["FixturesContextHolder"]

class FixturesContextHolder:
    _current: ClassVar[Self | None]
    calls: list[tuple[str, dict[str, Any]]]
    def __init__(self) -> None: ...
    @classmethod
    def current(cls) -> Self | None: ...
    def _record(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...
