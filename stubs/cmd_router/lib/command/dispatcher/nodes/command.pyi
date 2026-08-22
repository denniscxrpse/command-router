from .kinds import *
from _typeshed import Incomplete

__all__ = ["CommandNode"]

class CommandNode:
    kind: Incomplete
    name: Incomplete
    command: Incomplete
    children: list[CommandNode]
    def __init__(self, name: str, *, command: _Handler | None = None) -> None: ...
    @property
    def label(self) -> str: ...
    def add_child(self, child: CommandNode) -> CommandNode: ...
    def set_command(self, command: _Handler) -> CommandNode: ...
