from pathlib import Path
from typing import Any

from _typeshed import Incomplete

from pkg.lib.control import ControlResult
from pkg.lib.control.api import *
from pkg.lib.grammar.loader import *
from pkg.suggestions import *
from pkg.suite import *
from pkg.utils import Status

__all__ = ["REPL", "CommandRouter", "Lazy@59"]

_Dict = dict[str, Any]

class _Router:
    grammars: _Dict
    info: _Dict
    control: Incomplete
    def normalize(self, *t: _Dict) -> None: ...
    def lazy_init(self) -> None: ...
    def grammar_init(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | Status: ...
    @property
    def genesis_source(self) -> Path | None: ...
    def control_init(self) -> bool: ...

class CommandRouter:
    _was_i_initialized: bool
    _grammars: Incomplete
    _info: Incomplete
    control: Incomplete
    def __init__(self) -> None: ...
    @property
    def initialize(self) -> Status: ...
    @property
    def main(self) -> Status: ...
    def execute(self, command: Any) -> ControlResult: ...
    async def execute_async(self, command: Any) -> ControlResult: ...
    @property
    def deeper_level(self) -> Any: ...
    def _test_suite_loop(self) -> Status: ...
    def _serve_loop(self) -> Status: ...
    @staticmethod
    def _serve_fallback(text: str, message: str) -> None: ...
    def _handle_command(self, command: str) -> Outcome: ...

# Names in __all__ with no definition:
#   Lazy@59
#   REPL
