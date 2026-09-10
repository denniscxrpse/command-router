#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Compile compact control grammars into hand-built command trees.

This module is the lowering stage between the grammar parser and the command
dispatcher.  A control grammar is a mapping whose keys are command names and
whose values are strings in the notation understood by
``cmd_router.lib.control.grammar``.  The parser produces a small, private
syntax tree; this module turns that tree into the public command-node objects
exposed through ``CmdNode``.  Runtime command input is not parsed here.  The
resulting ``CmdNode.Dispatcher`` performs that work after compilation.

Compilation has four important stages:

1. Each grammar string is parsed by ``_GrammarParser``.  Syntax errors are
   represented by ``_GrammarSyntaxError`` and are allowed to travel back to
   the control API, which converts them into a structured initialization
   result.
2. ``_expand_sequence`` lowers the parser's nested terms into every concrete
   command path.  A path is represented as ``(terms, defaults)``: ``terms``
   contains the literal and argument terms that must appear in the command
   tree, while ``defaults`` contains argument values for terms that can be
   omitted from that path.
3. Every concrete path is merged into one tree rooted at a literal node named
   after the command.  Value reuses existing literal nodes.  Existing
   argument nodes are reused only when both their names and argument-type
   names match.  This sharing is what allows several alternatives to have a
   common prefix without creating ambiguous duplicate nodes.
4. A handler is attached to each terminal node, and the command root is
   registered with a fresh dispatcher.  Handlers look up the action mapping
   when they are invoked, so replacing ``command_action`` after initialization
   changes the action used by the already-built tree.

The expansion rules are intentionally simple and deterministic.  A literal or
argument with no default contributes one path containing itself.  An argument
with a default contributes two paths: one containing the argument and one
without it, with the default recorded for the latter.  A choice contributes
to the concatenation of the expansions of its alternatives.  An optional term
contributes an empty path plus the expansion of its body.  Sequences combine
their terms as a Cartesian product, merging the defaults from each selected
branch from left to right.  Consequently, a grammar such as
``<count:int=1> <item>`` creates a path for an explicit count and a second
path that accepts only ``<item>`` while passing ``count=1`` to the action.
Parsed command arguments always override compiler-supplied defaults.

The compiler recognizes the argument types ``word``, ``string``, ``int``
(``integer`` is an alias), and ``greedy`` (``greedy_string`` is an alias).
Argument-type instances are created on demand.  Greedy arguments are therefore
subject to the normal dispatcher invariant that they must be terminal.  A
malformed grammar can consequently fail either in the grammar parser or when
the corresponding command nodes are assembled; this module intentionally
does not hide either failure.

The built-in ``help`` command is handled here because it depends on the whole
grammar mapping.  When ``keep_help`` is true, a user-supplied ``help`` grammar
is skipped and a generated command returns the available command names and
``command_prefix``.  Its optional greedy target also returns the grammar text
for one named command.  When it is false, ``help`` is compiled like any other
command and no built-in replacement is registered.  An action missing from the
mapping is valid at compile time; invoking that command returns ``None``.  A
non-callable action is rejected while compiling, and a mapping changed to
contain a non-callable value after compilation fails when the late-bound
handler is invoked.

The functions in this file are private implementation helpers.  Callers
should normally use ``Control.initialize`` or ``Control.configure`` and then
the public ``CmdNode``/control APIs rather than constructing these intermediate
paths directly.
"""

from collections.abc import Callable, Mapping
from typing import Any

from cmd_router.lib.commands import CmdNode, CmdType
from cmd_router.utils import log

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
    """Expand one parsed term into concrete paths and omitted-value defaults.

    The first item in each returned pair is the sequence of terms that must
    be materialized as dispatcher nodes.  The second item is attached to the
    handler for that path and is used only when a grammar argument was omitted
    because it had a default value.  Keeping these two pieces separate is
    important: a defaulted argument still has an explicit path, but it also
    has an alternate path in which the argument node is absent.

    Literals and ordinary arguments have one expansion.  A defaulted argument
    has an explicit-argument expansion and an empty expansion carrying its
    default.  Choices concatenate the expansions of each alternative, while
    optional terms prepend an empty expansion to the expansion of their body.
    Unknown term objects are rejected rather than silently treated as
    literals because accepting them would make malformed parser/compiler
    boundaries difficult to diagnose.

    :raises _GrammarSyntaxError: If *term* is not one of the parser's term
        types.
    """
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
    """Expand a sequence by taking the Cartesian product of its terms.

    Expansion starts with one empty path.  For each term, every path produced
    so far is combined with every path produced by ``_expand(term)``.  Term
    tuples are concatenated in order, and defaults are copied before the next
    branch's defaults are applied.  If multiple selected terms use the same
    argument name, a later default replaces an earlier default in the
    resulting dictionary; the parser does not reject duplicate names.

    An empty sequence therefore produces one empty path, which lets the
    compiler represent a command that is valid immediately at its root.  The
    function deliberately performs no dispatcher validation; such checks are
    left to node construction after expansion.
    """
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
    """Create a fresh ``CmdType`` instance for a grammar type name.

    ``integer`` and ``greedy_string`` are accepted as readable aliases for
    ``int`` and ``greedy`` respectively.  The parser case-folds type names,
    and the mapping here also makes the accepted names explicit at the
    compiler boundary.  Returning a new instance on each call keeps this
    helper independent of the mutable state on argument-type objects while
    the tree-merging logic compares their public ``name`` attributes.

    :raises _GrammarSyntaxError: If *type_name* is not one of the supported
        names.
    """
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
    """Find the child of *parent* that represents *term*, if one exists.

    Literal nodes match by their exact value.  Argument nodes match by name
    and by the canonical name of their argument type, which means aliases such
    as ``integer``/``int`` share one node.  Choices and optional terms never
    reach this helper because ``_expand_sequence`` has already lowered them
    into paths.  Returning ``None`` asks the caller to create a new node.

    The helper intentionally searches only the immediate children.  Tree
    sharing is local to a path prefix; recursively searching descendants
    would change the grammar's nesting and could merge unrelated branches.
    """
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
    """Create a late-bound action wrapper for one expanded grammar path.

    *defaults* are copied when the wrapper is created, so the later mutation of the
    expansion dictionary cannot change the compiled path.  At invocation time
    the wrapper copies those values, overlays the parsed arguments, and then
    retrieves *command_name* from ``action_provider``.  Parsed values therefore
    take precedence over defaults, and the action mapping may be replaced
    after compilation without rebuilding the dispatcher.

    If no action is currently registered for the command, the wrapper returns
    ``None`` **and still counts as a valid dispatcher handler**.  If the current
    value exists but is not callable, a ``TypeError`` is raised at invocation;
    the control API converts that action failure into its structured execution
    result.  The provider is deliberately called only when the command is
    executed, not when this wrapper is constructed.
    """
    default_values = dict(defaults)

    def handler(**arguments: Any) -> Any:
        """Run the configured action with parsed arguments."""
        values = dict(default_values)
        values.update(arguments)
        action = action_provider().get(command_name)
        if action is not None and not callable(action):
            log.error("action for %r is no longer callable", command_name)
            raise TypeError(f"action for {command_name!r} must be callable")
        if action is None:
            log.warning("no action is registered for %r; returning None", command_name)
            return None
        log.debug("invoking action for %r with arguments %r", command_name, values)
        return action(**values)

    return handler


def _compile_grammars(
    grammars: _GrammarSource,
    action_provider: Callable[[], Mapping[str, Any]],
    keep_help: bool,
    command_prefix: str,
) -> CmdNode.Dispatcher:
    """Compile a grammar mapping into a new dispatcher.

    Each mapping entry must have a non-empty string command name and a string
    grammar expression.  The expression is parsed, expanded into concrete
    paths, merged into a literal-rooted tree, and registered with the returned
    dispatcher.  The action provider is sampled once for early validation and
    is retained by each generated handler for late lookup at execution time.

    ``keep_help`` controls the special built-in help branch.  If true, a
    grammar entry named ``help`` is ignored, and the returned dispatcher gets a
    ``help`` command whose result contains the non-help command names,
    *command_prefix*, and an optional target grammar.  If false, the supplied
    ``help`` grammar, *if any*, is compiled normally and no built-in branch is
    added.

    This is a compilation boundary rather than an error-normalization
    boundary.  It raises ``_GrammarSyntaxError`` for invalid grammar data and
    may also propagate ``TypeError``/``ValueError`` from action validation or
    command-node construction.  ``Control.configure`` is responsible for
    catching those failures and returning ``ControlInitialization`` data.

    :param grammars: Mapping from command names to compact grammar strings.
    :param action_provider: Callable returning the current command-action
        mapping.
    :param keep_help: Whether to install the generated help command.
    :param command_prefix: Prefix returned by the generated help action.
    :return: A dispatcher containing one registered root per compiled command.
    """
    actions = action_provider()
    log.info("starting compilation of %d grammar entr%s", len(grammars), "y" if len(grammars) == 1 else "ies")
    log.debug(
        "options (keep_help=%s, command_prefix=%r, actions=%s)",
        keep_help,
        command_prefix,
        tuple(actions),
    )
    dispatcher = CmdNode.Dispatcher()

    for command_name, syntax in grammars.items():
        log.debug("processing %r with syntax %r", command_name, syntax)
        if not isinstance(command_name, str) or not command_name:
            raise _GrammarSyntaxError("command names must be non-empty strings")
        if not isinstance(syntax, str):
            raise _GrammarSyntaxError(f"grammar for {command_name!r} must be a string")
        if command_name == "help" and keep_help:
            log.warning("skipping user-defined 'help' grammar because built-in help is enabled")
            continue

        action = actions.get(command_name)
        if action is not None and not callable(action):
            log.error("configured action for %r is not callable", command_name)
            raise _GrammarSyntaxError(f"action for {command_name!r} must be callable")

        expression = _GrammarParser(syntax).parse()
        paths = _expand_sequence(expression)
        log.debug("expanded %r into %d concrete path(s)", command_name, len(paths))
        root = CmdNode.Literal(command_name)
        for terms, defaults in paths:
            log.debug("materializing %r path terms=%r defaults=%r", command_name, terms, defaults)
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
        log.debug("registered command root %r", command_name)

    if keep_help:
        command_names = tuple(name for name in grammars if name != "help")
        command_syntax = {name: grammars[name] for name in command_names}

        def help_action(**arguments: Any) -> dict[str, Any]:
            """Return the available commands and an optional target grammar."""
            # Treat the help command as `help: [<target...>]`; where <target...> is the target
            # meant to return the syntax of an expected (existing) command.
            # Example usage: `/help say` -> `{..., "target": "say = "<message...>""}`.
            # Note: We treat <target...> as greedy because the given target must be literal.
            r: dict[str, Any] = {"commands": command_names, "prefix": command_prefix, "target": None}
            target = arguments.get("target")
            if target is None:
                log.debug("help overview requested")
            else:
                s = command_syntax.get(target)
                if s is None:
                    log.warning("help target for %r was not found!", target)
                else:
                    r["target"] = f'{target} = "{s}"'
                    log.debug("help target %r matched", target)
            return r

        help_node = CmdNode.Literal("help", command=help_action)
        help_node.add_child(CmdNode.Argument("target", CmdType.GreedyString(), command=help_action))
        dispatcher.register(help_node)
        log.info("installed built-in help for %d command(s)", len(command_names))

    log.info("compilation completed")
    return dispatcher
