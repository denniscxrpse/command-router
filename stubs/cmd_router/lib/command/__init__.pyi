from _typeshed import Incomplete
from cmd_router.lib.command.context import (
    CommandContext as _CommandContext,
    ParseError as _ParseError,
    ParseResult as _ParseResult,
)
from cmd_router.lib.command.dispatcher import (
    ArgumentNode as _ArgumentNode,
    CommandDispatcher as _CommandDispatcher,
    CommandNode as _CommandNode,
    LiteralNode as _LiteralNode,
    RootNode as _RootNode,
)
from cmd_router.lib.command.typing import (
    ArgumentType as _ArgumentType,
    GreedyString as _GreedyString,
    Int as _Int,
    String as _String,
    Word as _Word,
)
from cmd_router.utils.context import _Error
from typing import Final

__all__ = ["CmdError", "CmdType", "CmdParse", "CmdNode"]

class _CmdType:
    ArgumentType = _ArgumentType
    Word = _Word
    String = _String
    Int = _Int
    GreedyString = _GreedyString
    word: Incomplete
    string: Incomplete
    integer: Incomplete
    greedy_string: Incomplete

class _CmdParse:
    Context = _CommandContext
    Error = _ParseError
    Result = _ParseResult
    Tokenize: Incomplete

class _CmdNode:
    Base = _CommandNode
    Root = _RootNode
    Literal = _LiteralNode
    Argument = _ArgumentNode
    Dispatcher = _CommandDispatcher

CmdError: Final[type[_Error]]
CmdType: Final[type[_CmdType]]
CmdParse: Final[type[_CmdParse]]
CmdNode: Final[type[_CmdNode]]
