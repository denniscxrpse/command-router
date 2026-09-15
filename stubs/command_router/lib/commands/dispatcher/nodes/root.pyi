from collections.abc import Callable
from typing import Any

from _typeshed import Incomplete

from .command import *
from .kinds import *

_Handler = Callable[..., Any]

class RootNode(CommandNode):
    kind: Incomplete
    def __init__(self) -> None: ...
