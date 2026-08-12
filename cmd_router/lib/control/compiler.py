#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Build dispatcher trees from parsed control grammars."""

from collections.abc import Callable, Mapping
from typing import Any

from cmd_router.lib.command import CmdNode, CmdType

from .grammar import (
    _ArgumentTerm,
    _ChoiceTerm,
    _GrammarParser,
    _GrammarSyntaxError,
    _LiteralTerm,
    _OptionalTerm,
)

_Action = Callable[..., Any]
_GrammarSource = Mapping[str, str]


def _expand(term: Any) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Expand one grammar term into paths and defaults."""
    if isinstance(term, _LiteralTerm) or isinstance(term, _ArgumentTerm):
        if isinstance(term, _ArgumentTerm) and term.has_default:
            return [((term,), {}), ((), {term.name: term.default})]
        return [((term,), {})]

    if isinstance(term, _ChoiceTerm):
        paths: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        for alternative in term.alternatives:
            paths.extend(_expand_sequence(alternative))
        return paths

    if isinstance(term, _OptionalTerm):
        return [((), {}), *_expand(term.body)]

    raise _GrammarSyntaxError(f"unsupported grammar term: {term!r}")


def _expand_sequence(sequence: tuple[Any, ...]) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Expand a grammar sequence into terminal paths."""
    paths: list[tuple[tuple[Any, ...], dict[str, Any]]] = [((), {})]
    for term in sequence:
        next_paths: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        for prefix, prefix_defaults in paths:
            for suffix, suffix_defaults in _expand(term):
                defaults = dict(prefix_defaults)
                defaults.update(suffix_defaults)
                next_paths.append((prefix + suffix, defaults))
        paths = next_paths
    return paths


def _argument_type(type_name: str) -> Any:
    """Create the command argument type named by a grammar term."""
    types = {
        "word": CmdType.Word,
        "string": CmdType.String,
        "int": CmdType.Int,
        "integer": CmdType.Int,
        "greedy": CmdType.GreedyString,
        "greedy_string": CmdType.GreedyString,
    }
    selected = types.get(type_name)
    if selected is None:
        raise _GrammarSyntaxError(f"unsupported argument type {type_name!r}")
    return selected()


def _find_child(parent: Any, term: Any) -> Any | None:
    """Find the existing tree child matching a grammar term."""
    for child in parent.children:
        if isinstance(term, _LiteralTerm) and isinstance(child, CmdNode.Literal):
            if child.name == term.value:
                return child
        elif isinstance(term, _ArgumentTerm) and isinstance(child, CmdNode.Argument):
            if child.name == term.name and child.argument_type.name == _argument_type(term.type_name).name:
                return child
    return None


def _make_action_handler(
    command_name: str,
    action_provider: Callable[[], Mapping[str, Any]],
    defaults: Mapping[str, Any],
) -> _Action:
    """Create a handler that applies grammar defaults before dispatch."""
    default_values = dict(defaults)

    def handler(**arguments: Any) -> Any:
        """Run the configured action with parsed arguments."""
        values = dict(default_values)
        values.update(arguments)
        action = action_provider().get(command_name)
        if action is not None and not callable(action):
            raise TypeError(f"action for {command_name!r} must be callable")
        if action is None:
            return None
        return action(**values)

    return handler


def _compile_grammars(
    grammars: _GrammarSource,
    action_provider: Callable[[], Mapping[str, Any]],
    keep_help: bool,
    command_prefix: str,
) -> CmdNode.Dispatcher:
    """Compile grammar definitions into a command dispatcher."""
    dispatcher = CmdNode.Dispatcher()
    actions = action_provider()

    for command_name, syntax in grammars.items():
        if not isinstance(command_name, str) or not command_name:
            raise _GrammarSyntaxError("command names must be non-empty strings")
        if not isinstance(syntax, str):
            raise _GrammarSyntaxError(f"grammar for {command_name!r} must be a string")
        if command_name == "help" and keep_help:
            continue

        action = actions.get(command_name)
        if action is not None and not callable(action):
            raise _GrammarSyntaxError(f"action for {command_name!r} must be callable")

        expression = _GrammarParser(syntax).parse()
        paths = _expand_sequence(expression)
        root = CmdNode.Literal(command_name)
        for terms, defaults in paths:
            current = root
            for term in terms:
                child = _find_child(current, term)
                if child is None:
                    if isinstance(term, _LiteralTerm):
                        child = CmdNode.Literal(term.value)
                    else:
                        child = CmdNode.Argument(term.name, _argument_type(term.type_name))
                    current.add_child(child)
                current = child
            current.set_command(_make_action_handler(command_name, action_provider, defaults))
        dispatcher.register(root)

    if keep_help:
        command_names = tuple(name for name in grammars if name != "help")

        def help_action(**_arguments: Any) -> dict[str, Any]:
            """Return the available command names."""
            return {"commands": command_names, "prefix": command_prefix}

        dispatcher.register(CmdNode.Literal("help", command=help_action))

    return dispatcher
