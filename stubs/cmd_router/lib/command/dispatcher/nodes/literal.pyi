from .kinds import *
from .command import CommandNode as CommandNode
from _typeshed import Incomplete

class LiteralNode(CommandNode):
    kind: Incomplete
    def __init__(self, literal: str, *, command: _Handler | None = None) -> None: ...
