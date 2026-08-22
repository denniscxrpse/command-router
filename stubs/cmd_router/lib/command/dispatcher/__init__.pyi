from collections.abc import Callable
from typing import Any, Final

from _typeshed import Incomplete

from cmd_router.lib import *
from cmd_router.lib.command.context import *
from cmd_router.lib.command.dispatcher.nodes import *
from cmd_router.lib.command.typing import *
from cmd_router.utils.logger import *

__all__ = ["ArgumentNode", "CommandNode", "LiteralNode", "RootNode", "CommandDispatcher", "cmd_dispatcher"]

_Handler = Callable[..., Any]

class CommandDispatcher:
    root: Incomplete
    def __init__(self, root: RootNode | None = None) -> None: ...
    def register(self, node: CommandNode) -> CommandNode: ...
    def parse(self, command: str) -> ParseResult: ...
    def dispatch(self, command: str) -> ParseResult: ...
    def _walk(
        self, node: CommandNode, tokens: tuple[str, ...], index: int, args: dict[str, Any], original_input: str
    ) -> ParseResult | ParseError: ...
    def _incomplete(self, node: CommandNode, index: int, args: dict[str, Any]) -> ParseError: ...
    @staticmethod
    def _expected(node: CommandNode) -> tuple[str, ...]: ...
    @staticmethod
    def _best_error(errors: list[ParseError]) -> ParseError: ...

cmd_dispatcher: Final[CommandDispatcher]

# Names in __all__ with no definition:
#   ArgumentNode
#   CommandNode
#   LiteralNode
#   RootNode
