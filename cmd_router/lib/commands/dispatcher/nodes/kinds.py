#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("NodeKind",)

from enum import StrEnum


class NodeKind(StrEnum):
    """Protected enum of node kinds. Not exposed directly."""

    ROOT = "root"
    COMMAND = "command"
    ARGUMENT = "argument"
    LITERAL = "literal"
