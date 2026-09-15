#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Redirect: one primitive for aliases and repeating modifier chains."""

from collections.abc import Callable
from typing import Any

import pytest

from pkg.lib.commands import CmdNode, CmdType
from pkg.lib.control import ControlResultKinds
from pkg.sdk import argument, build_dispatcher, literal


def _say(**arguments: Any) -> Any:
    return arguments


def _tell(**arguments: Any) -> Any:
    return arguments


def _execute_dispatcher() -> Any:
    say = literal("say").then(argument("message", CmdType.greedy_string()).executes(_say))
    tell = literal("tell").then(
        argument("target", CmdType.word()).then(argument("message", CmdType.greedy_string()).executes(_tell))
    )
    msg = literal("msg").redirect(tell)
    execute = literal("execute")
    executor = argument("executor", CmdType.word()).redirect(execute)
    location = argument("location", CmdType.word()).redirect(execute)
    run = literal("run")
    execute.then(
        literal("as").then(executor),
        literal("at").then(location),
        run,
    )
    dispatcher = build_dispatcher(say, tell, msg, execute)
    run.redirect(dispatcher.root)
    return dispatcher


@pytest.mark.parametrize(
    ("command", "handler", "expected_args"),
    [
        ("say hello world", _say, {"message": "hello world"}),
        ("tell Alex hello world", _tell, {"target": "Alex", "message": "hello world"}),
        ("msg Alex hello world", _tell, {"target": "Alex", "message": "hello world"}),
        ("execute run say hello", _say, {"message": "hello"}),
        ("execute as Steve run say hello", _say, {"executor": "Steve", "message": "hello"}),
        (
            "execute as Steve at home run tell Alex hi",
            _tell,
            {"executor": "Steve", "location": "home", "target": "Alex", "message": "hi"},
        ),
        ("execute as A as B run say hi", _say, {"executor": "B", "message": "hi"}),
    ],
)
def test_redirect_alias_and_chain_parse_to_handlers(
    command: str, handler: Callable[..., Any], expected_args: dict[str, Any]
) -> None:
    dispatcher = _execute_dispatcher()

    result = dispatcher.parse(command)

    assert result.ok
    assert result.handler is handler
    assert result.context is not None
    assert result.context.parsed_args == expected_args
    assert result.context.cursor == len(result.context.tokens)


@pytest.mark.parametrize(
    ("command", "kind", "token_index", "expected"),
    [
        ("execute", ControlResultKinds.UNEXPECTED_COMMAND, 1, ("as", "at", "run")),
        ("execute as Steve", ControlResultKinds.UNEXPECTED_COMMAND, 3, ("as", "at", "run")),
        ("execute as Steve run", ControlResultKinds.UNEXPECTED_COMMAND, 4, ("say", "tell", "msg", "execute")),
        ("msg", ControlResultKinds.UNEXPECTED_COMMAND, 1, ("<target>",)),
    ],
)
def test_redirect_incomplete_reports_redirected_expectations(
    command: str, kind: ControlResultKinds, token_index: int, expected: tuple[str, ...]
) -> None:
    dispatcher = _execute_dispatcher()

    result = dispatcher.parse(command)

    assert not result.ok
    assert result.error is not None
    assert result.error.kind == kind
    assert result.error.token_index == token_index
    assert result.error.expected == expected


def test_direct_children_win_over_redirect() -> None:
    def direct() -> None:
        return None

    def fallback(**arguments: Any) -> Any:
        return arguments

    main = literal("base")
    main.then(literal("known").executes(direct))
    main.redirect(literal("other").then(argument("value", CmdType.word()).executes(fallback)))
    dispatcher = build_dispatcher(main)

    known = dispatcher.parse("base known")
    other = dispatcher.parse("base something")

    assert known.handler is direct
    assert other.handler is fallback
    assert other.context is not None
    assert other.context.args == {"value": "something"}


def test_hand_built_alias_matches_builder() -> None:
    hand_tell = CmdNode.Literal("tell")
    hand_target = CmdNode.Argument("target", CmdType.Word())
    hand_target.add_child(CmdNode.Argument("message", CmdType.GreedyString(), command=_tell))
    hand_tell.add_child(hand_target)
    hand_msg = CmdNode.Literal("msg")
    hand_msg.set_redirect(hand_tell)
    hand = CmdNode.Dispatcher()
    hand.register(hand_tell)
    hand.register(hand_msg)

    tell = literal("tell").then(
        argument("target", CmdType.word()).then(argument("message", CmdType.greedy_string()).executes(_tell))
    )
    built = build_dispatcher(tell, literal("msg").redirect(tell))

    for command in ("tell Alex hi", "msg Alex hi", "msg"):
        left = hand.parse(command)
        right = built.parse(command)
        assert left.ok == right.ok
        assert (left.context.args if left.context else None) == (right.context.args if right.context else None)
        if left.error is not None or right.error is not None:
            assert left.error is not None and right.error is not None
            assert left.error.kind == right.error.kind
            assert left.error.token_index == right.error.token_index
            assert left.error.expected == right.error.expected


def test_set_redirect_rejects_self_target() -> None:
    node = CmdNode.Literal("a")

    with pytest.raises(ValueError, match="cannot be the node itself"):
        node.set_redirect(node)


def test_set_redirect_rejects_redirect_only_cycle() -> None:
    first = CmdNode.Literal("a")
    second = CmdNode.Literal("b")
    first.set_redirect(second)

    with pytest.raises(ValueError, match="would create a cycle"):
        second.set_redirect(first)


def test_set_redirect_rejects_greedy_source() -> None:
    greedy = CmdNode.Argument("message", CmdType.GreedyString())

    with pytest.raises(ValueError, match="must be terminal"):
        greedy.set_redirect(CmdNode.Literal("later"))


def test_add_child_rejects_greedy_child_with_redirect() -> None:
    greedy = CmdNode.Argument("message", CmdType.GreedyString())
    greedy.redirect = CmdNode.Literal("target")

    with pytest.raises(ValueError, match="must be terminal"):
        CmdNode.Literal("root").add_child(greedy)


def test_set_redirect_rejects_non_nodes() -> None:
    with pytest.raises(TypeError, match="must be a CommandNode"):
        CmdNode.Literal("a").set_redirect("nope")  # ty: ignore[invalid-argument-type]


def test_builder_redirect_rejects_non_nodes() -> None:
    with pytest.raises(TypeError, match="builder or CommandNode"):
        literal("a").redirect("nope")  # ty: ignore[invalid-argument-type]


def test_builder_redirect_to_alias_forwards() -> None:
    target = literal("a").then(argument("x", CmdType.word()).executes(_say))
    dispatcher = build_dispatcher(target, literal("b").redirect_to(target))

    result = dispatcher.parse("b hello")

    assert result.ok
    assert result.handler is _say
    assert result.context is not None
    assert result.context.args == {"x": "hello"}


def test_forced_redirect_cycle_ends_as_structured_error() -> None:
    first = CmdNode.Literal("a")
    second = CmdNode.Literal("b")
    first.redirect = second
    second.redirect = first
    dispatcher = CmdNode.Dispatcher()
    dispatcher.register(first)

    result = dispatcher.parse("a")

    assert not result.ok
    assert result.error is not None
    assert result.error.kind == ControlResultKinds.UNEXPECTED_COMMAND
    assert result.error.message == "redirect cycle detected"


def test_build_redirect_grammar_uses_given_actions() -> None:
    from fixtures.grammars import build_redirect_grammar

    dispatcher = build_redirect_grammar({"say": _say, "tell": _tell})

    alias = dispatcher.parse("msg Alex hi")
    chained = dispatcher.parse("execute as Steve at home run tell Alex hi")

    assert alias.ok and alias.handler is _tell
    assert alias.context is not None
    assert alias.context.args == {"target": "Alex", "message": "hi"}
    assert chained.ok and chained.handler is _tell
    assert chained.context is not None
    assert chained.context.args == {"executor": "Steve", "location": "home", "target": "Alex", "message": "hi"}


def test_fixture_exposes_redirect_dispatcher_alongside_base() -> None:
    from fixtures import Fixtures as ExampleFixtures

    fixture = ExampleFixtures()

    alias = fixture.builder_redirect_dispatcher.parse("msg Alex hello world")
    chained = fixture.builder_redirect_dispatcher.parse("execute as Steve run say hello")
    base = fixture.builder_dispatcher.parse("advancement grant Alex only story done")

    assert alias.ok
    assert alias.context is not None
    assert alias.context.args == {"target": "Alex", "message": "hello world"}
    assert chained.ok
    assert chained.context is not None
    assert chained.context.args == {"executor": "Steve", "message": "hello"}
    assert base.ok
