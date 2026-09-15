from typing import Final

from _typeshed import Incomplete

from pkg.lib.commands.context import (
    CommandContext as _CommandContext,
)
from pkg.lib.commands.context import (
    ParseError as _ParseError,
)
from pkg.lib.commands.context import (
    ParseResult as _ParseResult,
)
from pkg.lib.commands.dispatcher import CommandDispatcher as _CommandDispatcher
from pkg.lib.commands.dispatcher.nodes import (
    ArgumentNode as _ArgumentNode,
)
from pkg.lib.commands.dispatcher.nodes import (
    CommandNode as _CommandNode,
)
from pkg.lib.commands.dispatcher.nodes import (
    LiteralNode as _LiteralNode,
)
from pkg.lib.commands.dispatcher.nodes import (
    RootNode as _RootNode,
)
from pkg.lib.commands.typing import (
    ArgumentType as _ArgumentType,
)
from pkg.lib.commands.typing import (
    GreedyString as _GreedyString,
)
from pkg.lib.commands.typing import (
    Int as _Int,
)
from pkg.lib.commands.typing import (
    String as _String,
)
from pkg.lib.commands.typing import (
    Word as _Word,
)
from pkg.utils import Status

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
