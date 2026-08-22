from typing import Final

from _typeshed import Incomplete

from cmd_router.lib.command.context import (
    CommandContext as _CommandContext,
)
from cmd_router.lib.command.context import (
    ParseError as _ParseError,
)
from cmd_router.lib.command.context import (
    ParseResult as _ParseResult,
)
from cmd_router.lib.command.dispatcher import (
    ArgumentNode as _ArgumentNode,
)
from cmd_router.lib.command.dispatcher import (
    CommandDispatcher as _CommandDispatcher,
)
from cmd_router.lib.command.dispatcher import (
    CommandNode as _CommandNode,
)
from cmd_router.lib.command.dispatcher import (
    LiteralNode as _LiteralNode,
)
from cmd_router.lib.command.dispatcher import (
    RootNode as _RootNode,
)
from cmd_router.lib.command.typing import (
    ArgumentType as _ArgumentType,
)
from cmd_router.lib.command.typing import (
    GreedyString as _GreedyString,
)
from cmd_router.lib.command.typing import (
    Int as _Int,
)
from cmd_router.lib.command.typing import (
    String as _String,
)
from cmd_router.lib.command.typing import (
    Word as _Word,
)
from cmd_router.utils.context import _Error

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
