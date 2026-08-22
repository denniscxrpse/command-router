from .kinds import *
from .command import CommandNode as CommandNode
from _typeshed import Incomplete

class RootNode(CommandNode):
    kind: Incomplete
    def __init__(self) -> None: ...
