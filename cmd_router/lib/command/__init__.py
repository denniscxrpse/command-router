#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Concise public namespaces for command parsing.

The implementation remains split across ``argument_type``, ``context``, and ``dispatcher``. Callers should use the
namespace aliases exported here, so the kind of command object is clear at the call site.
"""

__all__ = ("CmdError", "CmdNode", "CmdParse", "CmdType")

from typing import Final

from cmd_router.lib.command.context import CommandContext as _CommandContext
from cmd_router.lib.command.context import ParseError as _ParseError
from cmd_router.lib.command.context import ParseResult as _ParseResult
from cmd_router.lib.command.dispatcher import ArgumentNode as _ArgumentNode
from cmd_router.lib.command.dispatcher import CommandDispatcher as _CommandDispatcher
from cmd_router.lib.command.dispatcher import CommandNode as _CommandNode
from cmd_router.lib.command.dispatcher import LiteralNode as _LiteralNode
from cmd_router.lib.command.dispatcher import RootNode as _RootNode
from cmd_router.lib.command.typing import ArgumentType as _ArgumentType
from cmd_router.lib.command.typing import GreedyString as _GreedyString
from cmd_router.lib.command.typing import Int as _Int
from cmd_router.lib.command.typing import String as _String
from cmd_router.lib.command.typing import Word as _Word
from cmd_router.lib.command.typing import greedy as _greedy_string
from cmd_router.lib.command.typing import integer as _integer
from cmd_router.lib.command.typing import string as _string
from cmd_router.lib.command.typing import word as _word
from cmd_router.lib.tokenizer import tokenize as _tokenize
from cmd_router.utils.context import _Error


class _CmdType:
    """Namespace for argument type classes and factories."""

    ArgumentType = _ArgumentType
    Word = _Word
    String = _String
    Int = _Int
    GreedyString = _GreedyString
    word = staticmethod(_word)
    string = staticmethod(_string)
    integer = staticmethod(_integer)
    greedy_string = staticmethod(_greedy_string)


class _CmdParse:
    """Namespace for parse contexts, errors, results, and tokenization."""

    Context = _CommandContext
    Error = _ParseError
    Result = _ParseResult
    Tokenize = staticmethod(_tokenize)


class _CmdNode:
    """Namespace for the hand-built command tree and dispatcher."""

    Base = _CommandNode
    Root = _RootNode
    Literal = _LiteralNode
    Argument = _ArgumentNode
    Dispatcher = _CommandDispatcher


CmdError: Final[type[_Error]] = _Error
CmdType: Final[type[_CmdType]] = _CmdType
CmdParse: Final[type[_CmdParse]] = _CmdParse
CmdNode: Final[type[_CmdNode]] = _CmdNode
