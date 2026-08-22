from collections.abc import Callable
from typing import Any

from _typeshed import Incomplete

from cmd_router.lib.command.typing import *

from .command import *
from .kinds import *

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
