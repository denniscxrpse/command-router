#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("CommandNode",)

from collections.abc import Callable
from typing import Any

from .kinds import *

_Handler = Callable[..., Any]


class CommandNode:
    """Base node shared by literals and typed arguments."""

    kind = NodeKind.COMMAND

    def __init__(self, name: str, *, command: _Handler | None = None) -> None:
        self.name = name
        if command is not None and not callable(command):
            raise TypeError(f"command must be callable, got {type(command).__name__}")
        self.command = command
        self.children: list[CommandNode] = []

    @property
    def label(self) -> str:
        """Return the syntax shown when this node is expected next."""
        return self.name

    def add_child(self, child: CommandNode) -> CommandNode:
        """Attach *child* and return it for convenient hand-built trees."""
        if getattr(self, "greedy", False):
            raise ValueError("greedy argument nodes must be terminal")

        if not isinstance(child, CommandNode):
            raise TypeError(f"child must be a CommandNode, got {type(child).__name__}")

        if getattr(child, "greedy", False) and child.children:
            raise ValueError("greedy argument nodes must be terminal")

        if any(self._duplicates(existing, child) for existing in self.children):
            raise ValueError(f"duplicate child node: {child.label}")

        self.children.append(child)
        return child

    def set_command(self, command: _Handler) -> CommandNode:
        """Attach a handler to this node and return the node."""
        if not callable(command):
            raise TypeError(f"command must be callable, got {type(command).__name__}")
        self.command = command
        return self

    @staticmethod
    def _duplicates(left: CommandNode, right: CommandNode) -> bool:
        if left.kind == right.kind == NodeKind.LITERAL:
            return left.name == right.name
        if left.kind == right.kind == NodeKind.ARGUMENT:
            return left.name == right.name
        return False
