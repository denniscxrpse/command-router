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
        self.redirect: CommandNode | None = None

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

        if getattr(child, "greedy", False) and getattr(child, "redirect", None) is not None:
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

    def set_redirect(self, target: CommandNode) -> CommandNode:
        """Point this node at *target* and return the node.

        Parsing that reaches this node continues with *target*'s children
        without consuming a token, which expresses aliases and repeating
        modifier chains. Children are still tried first, so a redirect is a
        fallback continuation rather than a replacement.

        Fails fast when *target* is not a node, is this node itself, sits on
        a greedy source, or would close a redirect-only cycle.
        """
        if not isinstance(target, CommandNode):
            raise TypeError(f"redirect target must be a CommandNode, got {type(target).__name__}")
        if target is self:
            raise ValueError("redirect target cannot be the node itself")
        if getattr(self, "greedy", False):
            raise ValueError("greedy argument nodes must be terminal")
        seen: set[int] = {id(self)}
        current: CommandNode | None = target
        while current is not None:
            if id(current) in seen:
                raise ValueError("redirect would create a cycle")
            seen.add(id(current))
            current = current.redirect
        self.redirect = target
        return self

    @staticmethod
    def _duplicates(left: CommandNode, right: CommandNode) -> bool:
        if left.kind == right.kind == NodeKind.LITERAL:
            return left.name == right.name
        if left.kind == right.kind == NodeKind.ARGUMENT:
            return left.name == right.name
        return False
