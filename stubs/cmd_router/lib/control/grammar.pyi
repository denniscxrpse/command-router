from cmd_router.utils.logger import log as log
from dataclasses import dataclass
from typing import Any

class _GrammarSyntaxError(ValueError): ...

@dataclass(frozen=True, slots=True)
class _LiteralTerm:
    value: str

@dataclass(frozen=True, slots=True)
class _ArgumentTerm:
    name: str
    type_name: str
    default: Any = ...
    has_default: bool = ...

@dataclass(frozen=True, slots=True)
class _ChoiceTerm:
    alternatives: tuple[tuple[Any, ...], ...]

@dataclass(frozen=True, slots=True)
class _OptionalTerm:
    body: _ChoiceTerm

class _GrammarParser:
    def __init__(self, source: str) -> None: ...
    def parse(self) -> tuple[Any, ...]: ...
