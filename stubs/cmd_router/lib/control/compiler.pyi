from collections.abc import Callable, Mapping
from typing import Any

from cmd_router.lib.command import CmdNode as CmdNode
from cmd_router.lib.command import CmdType as CmdType
from cmd_router.utils.logger import log as log

from .grammar import (
    _ArgumentTerm as _ArgumentTerm,
)
from .grammar import (
    _ChoiceTerm as _ChoiceTerm,
)
from .grammar import (
    _GrammarParser as _GrammarParser,
)
from .grammar import (
    _GrammarSyntaxError as _GrammarSyntaxError,
)
from .grammar import (
    _LiteralTerm as _LiteralTerm,
)
from .grammar import (
    _OptionalTerm as _OptionalTerm,
)

_Action = Callable[..., Any]
_GrammarSource = Mapping[str, str]

def _expand(term: Any) -> list[tuple[tuple[Any, ...], dict[str, Any]]]: ...
def _expand_sequence(sequence: tuple[Any, ...]) -> list[tuple[tuple[Any, ...], dict[str, Any]]]: ...
def _argument_type(type_name: str) -> Any: ...
def _find_child(parent: Any, term: Any) -> Any | None: ...
def _make_action_handler(
    command_name: str, action_provider: Callable[[], Mapping[str, Any]], defaults: Mapping[str, Any]
) -> _Action: ...
def _compile_grammars(
    grammars: _GrammarSource, action_provider: Callable[[], Mapping[str, Any]], keep_help: bool, command_prefix: str
) -> CmdNode.Dispatcher: ...
