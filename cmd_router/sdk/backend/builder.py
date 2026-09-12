#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Brigadier-inspired builder for the hand-built command tree.

This module is Phase 7: ergonomics after correctness.  It introduces no new
matching behavior.  Every builder delegates to the same ``CommandNode``
primitives used by hand-built trees:

* ``then`` calls ``CommandNode.add_child`` (so greedy-terminal and duplicate
  checks fail fast at build time, exactly as before).
* ``executes`` calls ``CommandNode.set_command`` (so handler validation is
  identical).
* ``build`` returns the underlying node; ``build_dispatcher`` registers built
  roots on a fresh ``CommandDispatcher``.

The intended shape is:

.. code-block:: python

    dispatcher = build_dispatcher(
        literal("say").then(
            argument("message", CmdType.greedy_string()).executes(say_handler)
        ),
        literal("tell").then(
            argument("target", CmdType.word()).then(
                argument("message", CmdType.greedy_string()).executes(tell_handler)
            )
        ),
    )

Choices are multiple ``then`` calls on one parent (``then`` is variadic, so
``literal("gamemode").then(survival, creative, ...)`` is one call).
Optionals are a parent with ``executes`` plus a child with ``executes``;
for example ``gamemode creative`` executes on the mode node, and
``gamemode creative <target>`` executes on the target node.  No separate
choice/optional node type exists because the dispatcher already expresses
both through shared prefixes and terminal handlers.

``then`` accepts builders or already-built ``CommandNode`` objects and always
returns the parent builder, so nesting expresses depth:

.. code-block:: python

    literal("tell").then(
        argument("target", word()).then(
            argument("message", greedy()).executes(handler)
        )
    )

Use ``build()`` when a caller needs the raw node (for mixing builder and
hand-built subtrees), and ``build_dispatcher`` when a caller wants a ready
dispatcher in one expression.
"""

from collections.abc import Callable
from typing import Any, Self

from cmd_router.lib.commands.dispatcher import CommandDispatcher
from cmd_router.lib.commands.dispatcher.nodes import ArgumentNode, CommandNode, LiteralNode
from cmd_router.lib.commands.typing import ArgumentType
from cmd_router.utils import log

__all__ = (
    "ArgumentBuilder",
    "LiteralBuilder",
    "NodeBuilder",
    "argument",
    "build_dispatcher",
    "literal",
)

_Handler = Callable[..., Any]


class NodeBuilder:
    """Wrap one command node and expose Brigadier-style chaining.

    The wrapper owns no matching logic.  It forwards structure to the wrapped
    node so builder-built trees and hand-built trees fail and parse the same
    way.  All chaining methods return ``self`` (the parent), not the child.
    """

    def __init__(self, node: CommandNode) -> None:
        """Store *node* as the build target.

        :raises TypeError: If *node* is not a ``CommandNode``.
        """
        if not isinstance(node, CommandNode):
            raise TypeError(f"node must be a CommandNode, got {type(node).__name__}")
        self._node = node
        log.debug("builder created for node %r", node.label or "<root>")

    @property
    def node(self) -> CommandNode:
        """Return the underlying command node."""
        return self._node

    @property
    def name(self) -> str:
        """Return the wrapped node's name."""
        return self._node.name

    def then(self, *children: "NodeBuilder | CommandNode") -> Self:  # noqa: UP037
        """Attach children and return this builder.

        Each child may be another builder (used via its ``build()``) or an
        already-built node.  At least one child is required.  Greedy-terminal
        and duplicate errors propagate from ``add_child`` unchanged.

        Multiple children express a choice at this position:

        .. code-block:: python

            literal("debug").then(literal("on"), literal("off"))
        """
        if not children:
            raise ValueError("then() requires at least one child")
        for child in children:
            if isinstance(child, NodeBuilder):
                target = child.build()
            elif isinstance(child, CommandNode):
                target = child
            else:
                raise TypeError(f"child must be a builder or CommandNode, got {type(child).__name__}")
            log.debug("builder attaching %r under %r", target.label, self._node.label or "<root>")
            self._node.add_child(target)
        return self

    def executes(self, handler: _Handler) -> Self:
        """Attach *handler* to this node and return this builder.

        Attaching at an intermediate node makes its trailing children
        optional (both the prefix and the longer path parse).  Attaching only
        at a leaf makes that full path required.
        """
        log.debug("builder setting handler on %r", self._node.label or "<root>")
        self._node.set_command(handler)
        return self

    def build(self) -> CommandNode:
        """Return the underlying command node."""
        return self._node


class LiteralBuilder(NodeBuilder):
    """Build one exact-token node."""

    def __init__(self, name: str, *, executes: _Handler | None = None) -> None:
        """Create a literal builder for *name*.

        :raises ValueError: If *name* is not a non-empty string.
        :raises TypeError: If *executes* is not callable.
        """
        super().__init__(LiteralNode(name, command=executes))


class ArgumentBuilder(NodeBuilder):
    """Build one typed-argument node."""

    def __init__(
        self, name: str, arg_type: ArgumentType[Any] | None = None, *, executes: _Handler | None = None
    ) -> None:
        """Create an argument builder for *name* using *arg_type*.

        A ``None`` type uses the default word-like type, matching
        ``ArgumentNode``.  Class values are instantiated; instances are used
        as-is after validating they expose ``parse``.

        :raises ValueError: If *name* is empty.
        :raises TypeError: If *arg_type* has no callable ``parse`` or
            *executes* is not callable.
        """
        super().__init__(ArgumentNode(name, arg_type, command=executes))

    @property
    def argument_type(self) -> ArgumentType[Any]:
        """Return the wrapped argument node's type."""
        node = self._node
        assert isinstance(node, ArgumentNode)
        return node.argument_type  # ty: ignore[invalid-return-type]


def literal(name: str, executes: _Handler | None = None) -> LiteralBuilder:
    """Start a literal branch matching exactly *name*.

    Pass ``executes`` for one-liners, or call ``.executes(handler)`` after
    chaining ``.then(...)`` for deeper trees.
    """
    return LiteralBuilder(name, executes=executes)


def argument(name: str, arg_type: ArgumentType[Any] | None = None, executes: _Handler | None = None) -> ArgumentBuilder:
    """Start an argument branch capturing *name* with *arg_type*.

    ``arg_type`` follows ``ArgumentNode`` (instances, classes, or ``None``
    for the default).  Greedy types must stay terminal; ``then`` on a greedy
    node raises ``ValueError`` through ``add_child``.
    """
    return ArgumentBuilder(name, arg_type, executes=executes)


def build_dispatcher(*roots: "NodeBuilder | CommandNode") -> CommandDispatcher:  # noqa: UP037
    """Build a dispatcher from builder or node roots.

    Each root is built (when a builder) and registered in order.  Duplicate
    top-level literals raise ``ValueError`` through ``register``/``add_child``,
    exactly as hand-built registration does.

    :return: A fresh dispatcher containing one root per argument.
    """
    dispatcher = CommandDispatcher()
    for root in roots:
        if isinstance(root, NodeBuilder):
            target = root.build()
        elif isinstance(root, CommandNode):
            target = root
        else:
            raise TypeError(f"root must be a builder or CommandNode, got {type(root).__name__}")
        log.debug("registering built root %r", target.name)
        dispatcher.register(target)
    return dispatcher
