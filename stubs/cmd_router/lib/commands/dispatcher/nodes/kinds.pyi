from enum import StrEnum

__all__ = ["NodeKind"]

class NodeKind(StrEnum):
    ROOT = "root"
    COMMAND = "command"
    ARGUMENT = "argument"
    LITERAL = "literal"
