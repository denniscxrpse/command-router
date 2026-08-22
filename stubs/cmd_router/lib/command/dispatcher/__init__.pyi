from cmd_router.lib import *
from cmd_router.lib.command.context import *
from cmd_router.lib.command.dispatcher.nodes import *
from cmd_router.lib.command.typing import *
from cmd_router.utils.logger import *
from _typeshed import Incomplete
from typing import Final

__all__ = ["ArgumentNode", "CommandNode", "LiteralNode", "RootNode", "CommandDispatcher", "cmd_dispatcher"]

class CommandDispatcher:
    root: Incomplete
    def __init__(self, root: RootNode | None = None) -> None: ...
    def register(self, node: CommandNode) -> CommandNode: ...
    def parse(self, command: str) -> ParseResult: ...
    def dispatch(self, command: str) -> ParseResult: ...

cmd_dispatcher: Final[CommandDispatcher]

# Names in __all__ with no definition:
#   ArgumentNode
#   CommandNode
#   LiteralNode
#   RootNode
