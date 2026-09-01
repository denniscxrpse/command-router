from _typeshed import Incomplete
from cmd_router.lib.commands.context import (
    CommandContext as _CommandContext,
    ParseError as _ParseError,
    ParseResult as _ParseResult,
)
from cmd_router.lib.commands.dispatcher import CommandDispatcher as _CommandDispatcher
from cmd_router.lib.commands.dispatcher.nodes import (
    ArgumentNode as _ArgumentNode,
    CommandNode as _CommandNode,
    LiteralNode as _LiteralNode,
    RootNode as _RootNode,
)
from cmd_router.lib.commands.typing import (
    ArgumentType as _ArgumentType,
    GreedyString as _GreedyString,
    Int as _Int,
    String as _String,
    Word as _Word,
)
from cmd_router.utils.context import Error
from typing import Final

__all__ = ["CmdError", "CmdType", "CmdParse", "CmdNode"]

CmdError: Final[type[Error]]

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
