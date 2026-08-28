from .kinds import *
from .command import CommandNode as CommandNode
from _typeshed import Incomplete
from collections.abc import Callable
from typing import Any

_Handler = Callable[..., Any]

class RootNode(CommandNode):
    kind: Incomplete
    def __init__(self) -> None: ...
