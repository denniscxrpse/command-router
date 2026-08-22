from _typeshed import Incomplete
from cmd_router.utils.context import _Error
from typing import Final

__all__ = ["CmdError", "CmdType", "CmdParse", "CmdNode"]

class _CmdType:
    ArgumentType: Incomplete
    Word: Incomplete
    String: Incomplete
    Int: Incomplete
    GreedyString: Incomplete
    word: Incomplete
    string: Incomplete
    integer: Incomplete
    greedy_string: Incomplete

class _CmdParse:
    Context: Incomplete
    Error: Incomplete
    Result: Incomplete
    Tokenize: Incomplete

class _CmdNode:
    Base: Incomplete
    Root: Incomplete
    Literal: Incomplete
    Argument: Incomplete
    Dispatcher: Incomplete

CmdError: Final[type[_Error]]
CmdType: Final[type[_CmdType]]
CmdParse: Final[type[_CmdParse]]
CmdNode: Final[type[_CmdNode]]
