from cmd_router.lib.commands.typing import *
from .command import *
from .kinds import *
from _typeshed import Incomplete
from collections.abc import Callable
from typing import Any

_Handler = Callable[..., Any]

class ArgumentNode(CommandNode):
    kind: Incomplete
    argument_type: Incomplete
    def __init__(
        self, name: str, argument_type: ArgumentType[Any] | None = None, *, command: _Handler | None = None
    ) -> None: ...
    @property
    def greedy(self) -> bool: ...
    @property
    def label(self) -> str: ...
