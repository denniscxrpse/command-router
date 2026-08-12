#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


__all__ = (
    "CommandContext",
    "ParseError",
    "ParseResult",
    "cmd_context",
)

from dataclasses import dataclass
from typing import Final

from cmd_router.lib.command.context.parse import CommandContext
from cmd_router.lib.command.context.parse.err import ParseError
from cmd_router.lib.command.context.parse.result import ParseResult


@dataclass
class _Context:
    """Namespace reserved for shared command-context helpers."""

    ...


cmd_context: Final[_Context] = _Context()
