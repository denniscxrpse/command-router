#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from collections.abc import Callable
from typing import Any

from .command import *
from .kinds import *

_Handler = Callable[..., Any]


class LiteralNode(CommandNode):
    """A node that matches one exact token."""

    kind = NodeKind.LITERAL

    def __init__(self, literal: str, *, command: _Handler | None = None) -> None:
        if not isinstance(literal, str) or not literal:
            raise ValueError("literal must be a non-empty string")
        super().__init__(literal, command=command)
