#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

#  The Clear BSD License

__all__ = ("NodeKind",)

from enum import StrEnum


class NodeKind(StrEnum):
    ROOT = "root"
    COMMAND = "command"
    ARGUMENT = "argument"
    LITERAL = "literal"
