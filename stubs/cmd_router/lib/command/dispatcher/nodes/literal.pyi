from collections.abc import Callable
from typing import Any

from _typeshed import Incomplete

from .command import CommandNode as CommandNode
from .kinds import *

_Handler = Callable[..., Any]

class LiteralNode(CommandNode):
    kind: Incomplete
    def __init__(self, literal: str, *, command: _Handler | None = None) -> None: ...
