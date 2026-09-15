from typing import Final

from _typeshed import Incomplete

from command_router.lib.commands.context import (
    CommandContext as _CommandContext,
)
from command_router.lib.commands.context import (
    ParseError as _ParseError,
)
from command_router.lib.commands.context import (
    ParseResult as _ParseResult,
)
from command_router.lib.commands.dispatcher import CommandDispatcher as _CommandDispatcher
from command_router.lib.commands.dispatcher.nodes import (
    ArgumentNode as _ArgumentNode,
)
from command_router.lib.commands.dispatcher.nodes import (
    CommandNode as _CommandNode,
)
from command_router.lib.commands.dispatcher.nodes import (
    LiteralNode as _LiteralNode,
)
from command_router.lib.commands.dispatcher.nodes import (
    RootNode as _RootNode,
)
from command_router.lib.commands.typing import (
    ArgumentType as _ArgumentType,
)
from command_router.lib.commands.typing import (
    GreedyString as _GreedyString,
)
from command_router.lib.commands.typing import (
    Int as _Int,
)
from command_router.lib.commands.typing import (
    String as _String,
)
from command_router.lib.commands.typing import (
    Word as _Word,
)
from command_router.utils import Status

__all__ = ["CmdError", "CmdType", "CmdParse", "CmdNode"]

CmdError: Final[type[Status]]

class CmdType:
    ArgumentType = _ArgumentType
    Word = _Word
    String = _String
    Int = _Int
    GreedyString = _GreedyString
    word: Incomplete
    string: Incomplete
    integer: Incomplete
    greedy_string: Incomplete

class CmdParse:
    Context = _CommandContext
    Error = _ParseError
    Result = _ParseResult
    Tokenize: Incomplete

class CmdNode:
    Base = _CommandNode
    Root = _RootNode
    Literal = _LiteralNode
    Argument = _ArgumentNode
    Dispatcher = _CommandDispatcher
