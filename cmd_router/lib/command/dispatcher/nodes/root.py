#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


from collections.abc import Callable
from typing import Any

from cmd_router.lib.command.dispatcher.kinds import *

from .command import CommandNode

_Handler = Callable[..., Any]


class RootNode(CommandNode):
    """The invisible root of a command tree."""

    kind = NodeKind.ROOT

    def __init__(self) -> None:
        super().__init__("")
