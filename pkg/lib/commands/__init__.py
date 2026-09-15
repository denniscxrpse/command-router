#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Concise public namespaces for command parsing.

The implementation remains split across ``argument_type``, ``context``,
and ``dispatcher``. Callers should use the namespace aliases exported here,
so the kind of command object is clear at the call site.
"""

__all__ = ("CmdError", "CmdNode", "CmdParse", "CmdType")

from typing import Final, final

from pkg.lib.commands.context import CommandContext as _CommandContext
from pkg.lib.commands.context import ParseError as _ParseError
from pkg.lib.commands.context import ParseResult as _ParseResult
from pkg.lib.commands.dispatcher import CommandDispatcher as _CommandDispatcher
from pkg.lib.commands.dispatcher import tokenize
from pkg.lib.commands.dispatcher.nodes import ArgumentNode as _ArgumentNode
from pkg.lib.commands.dispatcher.nodes import CommandNode as _CommandNode
from pkg.lib.commands.dispatcher.nodes import LiteralNode as _LiteralNode
from pkg.lib.commands.dispatcher.nodes import RootNode as _RootNode
from pkg.lib.commands.typing import ArgumentType as _ArgumentType
from pkg.lib.commands.typing import GreedyString as _GreedyString
from pkg.lib.commands.typing import Int as _Int
from pkg.lib.commands.typing import String as _String
from pkg.lib.commands.typing import Word as _Word
from pkg.lib.commands.typing import greedy as _greedy_string
from pkg.lib.commands.typing import integer as _integer
from pkg.lib.commands.typing import string as _string
from pkg.lib.commands.typing import word as _word
from pkg.utils import IStatus, Status

CmdError: Final[type[Status]] = IStatus


@final
class CmdType:
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


@final
class CmdParse:
    """Namespace for parse contexts, errors, results, and tokenization."""

    Context = _CommandContext
    Error = _ParseError
    Result = _ParseResult
    Tokenize = staticmethod(tokenize)


@final
class CmdNode:
    """Namespace for the hand-built commands tree and dispatcher."""

    Base = _CommandNode
    Root = _RootNode
    Literal = _LiteralNode
    Argument = _ArgumentNode
    Dispatcher = _CommandDispatcher
