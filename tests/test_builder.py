#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Phase 7 builder: same trees, pleasanter registration."""

from collections.abc import Callable
from typing import Any

import pytest

from cmd_router.lib.commands import CmdNode, CmdType
from cmd_router.lib.control import ControlResultKinds
from cmd_router.sdk import argument, build_dispatcher, literal
from cmd_router.sdk.backend.builder import ArgumentBuilder, LiteralBuilder


def _say(**arguments: Any) -> Any:
    return arguments


def _tell(**arguments: Any) -> Any:
    return arguments


def _gamemode(**arguments: Any) -> Any:
    return arguments


def _advancement(**arguments: Any) -> Any:
    return arguments


def _tp(**arguments: Any) -> Any:
    return arguments


def _debug(**arguments: Any) -> Any:
    return arguments


def _builder_dispatcher() -> Any:
    say = literal("say").then(argument("message", CmdType.greedy_string()).executes(_say))

    tell = literal("tell").then(
        argument("target", CmdType.word()).then(argument("message", CmdType.greedy_string()).executes(_tell))
    )

    gamemode = literal("gamemode").then(
        *[
            literal(mode).executes(_gamemode).then(argument("target", CmdType.word()).executes(_gamemode))
            for mode in ("survival", "creative", "adventure", "spectator")
        ]
    )

    advancement_roots = []
    for action in ("grant", "revoke"):
        target = argument("target", CmdType.word())
        target.then(literal("*").executes(_advancement))
        adv = argument("advancement", CmdType.word()).executes(_advancement)
        adv.then(argument("criterion", CmdType.word()).executes(_advancement))
        target.then(literal("only").then(adv))
        advancement_roots.append(literal(action).then(target))
    advancement = literal("advancement").then(*advancement_roots)

    tp = literal("tp").then(
        argument("x", CmdType.integer()).then(
            argument("y", CmdType.integer()).then(argument("z", CmdType.integer()).executes(_tp))
        )
    )

    debug = literal("debug").then(
        literal("on").executes(_debug),
        literal("off").executes(_debug),
    )

    return build_dispatcher(say, tell, gamemode, advancement, tp, debug)


@pytest.mark.parametrize(
    ("command", "handler", "expected_args"),
    [
        ("say hello world", _say, {"message": "hello world"}),
        ('tell Alex "hello world"', _tell, {"target": "Alex", "message": "hello world"}),
        ("gamemode creative", _gamemode, {}),
        ("gamemode spectator Alex", _gamemode, {"target": "Alex"}),
        ("advancement grant Alex *", _advancement, {"target": "Alex"}),
        ("advancement revoke Alex only story", _advancement, {"target": "Alex", "advancement": "story"}),
        (
            'advancement grant Alex only story "done"',
            _advancement,
            {"target": "Alex", "advancement": "story", "criterion": "done"},
        ),
        ("tp 10 -2 3", _tp, {"x": 10, "y": -2, "z": 3}),
        ("debug off", _debug, {}),
    ],
)
def test_builder_fixtures_parse_to_handlers_and_context(
    command: str, handler: Callable[..., Any], expected_args: dict[str, Any]
) -> None:
    dispatcher = _builder_dispatcher()

    result = dispatcher.parse(command)

    assert result.ok
    assert result.handler is handler
    assert result.context is not None
    assert result.context.original_input == command
    assert result.context.parsed_args == expected_args
    assert result.context.cursor == len(result.context.tokens)


@pytest.mark.parametrize(
    ("command", "kind", "token_index", "expected"),
    [
        (
            "gamemode hardcore",
            ControlResultKinds.UNEXPECTED_TOKEN,
            1,
            ("survival", "creative", "adventure", "spectator"),
        ),
        ("tell Alex", ControlResultKinds.UNEXPECTED_COMMAND, 2, ("<message...>",)),
        ("advancement grant Alex only", ControlResultKinds.UNEXPECTED_COMMAND, 4, ("<advancement>",)),
        ("tp 1 nope 3", ControlResultKinds.INVALID_ARGUMENT, 2, ("<y:int>",)),
    ],
)
def test_builder_failures_match_hand_built_expectations(
    command: str, kind: ControlResultKinds, token_index: int, expected: tuple[str, ...]
) -> None:
    dispatcher = _builder_dispatcher()

    result = dispatcher.parse(command)

    assert not result.ok
    assert result.error is not None
    assert result.error.kind == kind
    assert result.error.token_index == token_index
    assert result.error.expected == expected


def test_builder_matches_hand_built_tree() -> None:
    hand = CmdNode.Dispatcher()

    say = CmdNode.Literal("say")
    say.add_child(CmdNode.Argument("message", CmdType.GreedyString(), command=_say))
    hand.register(say)

    tell = CmdNode.Literal("tell")
    tell_target = CmdNode.Argument("target", CmdType.Word())
    tell_target.add_child(CmdNode.Argument("message", CmdType.GreedyString(), command=_tell))
    tell.add_child(tell_target)
    hand.register(tell)

    gamemode = CmdNode.Literal("gamemode")
    for mode in ("survival", "creative", "adventure", "spectator"):
        mode_node = CmdNode.Literal(mode, command=_gamemode)
        mode_node.add_child(CmdNode.Argument("target", CmdType.Word(), command=_gamemode))
        gamemode.add_child(mode_node)
    hand.register(gamemode)

    advancement = CmdNode.Literal("advancement")
    for action in ("grant", "revoke"):
        action_node = CmdNode.Literal(action)
        target_node = CmdNode.Argument("target", CmdType.Word())
        target_node.add_child(CmdNode.Literal("*", command=_advancement))

        only_node = CmdNode.Literal("only")
        advancement_node = CmdNode.Argument("advancement", CmdType.Word(), command=_advancement)
        advancement_node.add_child(CmdNode.Argument("criterion", CmdType.Word(), command=_advancement))
        only_node.add_child(advancement_node)

        target_node.add_child(only_node)
        action_node.add_child(target_node)
        advancement.add_child(action_node)
    hand.register(advancement)

    tp = CmdNode.Literal("tp")
    x_node = CmdNode.Argument("x", CmdType.Int())
    y_node = CmdNode.Argument("y", CmdType.Int())
    y_node.add_child(CmdNode.Argument("z", CmdType.Int(), command=_tp))
    x_node.add_child(y_node)
    tp.add_child(x_node)
    hand.register(tp)

    debug = CmdNode.Literal("debug")
    debug.add_child(CmdNode.Literal("on", command=_debug))
    debug.add_child(CmdNode.Literal("off", command=_debug))
    hand.register(debug)

    built = _builder_dispatcher()

    cases = [
        "say hello world",
        "tell Alex hello",
        "gamemode creative Alex",
        "advancement grant Alex only story done",
        "tp 1 2 3",
        "debug on",
        "gamemode hardcore",
        "tell Alex",
        "tp 1 nope 3",
        "",
    ]
    for command in cases:
        left = hand.parse(command)
        right = built.parse(command)
        assert left.ok == right.ok
        assert (left.context.args if left.context else None) == (right.context.args if right.context else None)
        if left.error is not None or right.error is not None:
            assert left.error is not None and right.error is not None
            assert left.error.kind == right.error.kind
            assert left.error.token_index == right.error.token_index
            assert left.error.expected == right.error.expected


def test_then_and_executes_return_parent_for_chaining() -> None:
    parent = literal("root")
    child = literal("known").executes(_say)

    assert parent.then(child) is parent
    assert parent.executes(_tell) is parent
    assert parent.build().command is _tell
    assert parent.build().children[0].command is _say


def test_then_accepts_nodes_and_builders_and_requires_a_child() -> None:
    parent = literal("root")
    node = CmdNode.Literal("known", command=_say)
    parent.then(node)
    parent.then(argument("value", CmdType.word()).executes(_tell))

    dispatcher = build_dispatcher(parent)
    assert dispatcher.parse("root known").handler is _say
    assert dispatcher.parse("root other").handler is _tell

    with pytest.raises(ValueError, match="at least one child"):
        literal("empty").then()


def test_then_rejects_non_nodes() -> None:
    with pytest.raises(TypeError, match="builder or CommandNode"):
        literal("root").then("nope")  # ty: ignore[invalid-argument-type]


def test_greedy_and_duplicate_rules_match_hand_built() -> None:
    with pytest.raises(ValueError, match="greedy argument nodes must be terminal"):
        argument("message", CmdType.greedy_string()).then(literal("later"))

    with pytest.raises(ValueError, match="duplicate child node"):
        literal("root").then(literal("same"), literal("same"))

    with pytest.raises(ValueError, match="literal must be a non-empty string"):
        literal("")

    with pytest.raises(ValueError, match="argument name must be a non-empty string"):
        argument("", CmdType.word())

    with pytest.raises(TypeError, match="command must be callable"):
        literal("root").executes("nope")  # ty: ignore[invalid-argument-type]


def test_build_returns_raw_nodes_for_mixed_trees() -> None:
    built = literal("say").then(argument("message", CmdType.greedy_string()).executes(_say)).build()

    assert isinstance(built, CmdNode.Literal)
    assert built.name == "say"
    assert isinstance(built.children[0], CmdNode.Argument)

    hand_root = CmdNode.Literal("mix")
    hand_root.add_child(built)
    dispatcher = build_dispatcher(hand_root)
    result = dispatcher.parse("mix say hello")
    assert result.ok
    assert result.handler is _say
    assert result.context is not None
    assert result.context.args == {"message": "hello"}


def test_build_dispatcher_registers_in_order_and_validates_roots() -> None:
    dispatcher = build_dispatcher(literal("a").then(literal("b").executes(_say)), literal("c").executes(_tell))

    assert dispatcher.parse("a b").handler is _say
    assert dispatcher.parse("c").handler is _tell

    with pytest.raises(TypeError, match="builder or CommandNode"):
        build_dispatcher("nope")  # ty: ignore[invalid-argument-type]


def test_factories_expose_typed_builders() -> None:
    assert isinstance(literal("x"), LiteralBuilder)
    assert isinstance(argument("y", CmdType.integer()), ArgumentBuilder)
    assert argument("y", CmdType.integer()).argument_type.name == "int"
    assert literal("x", executes=_say).build().command is _say
    assert argument("y", CmdType.word(), executes=_tell).build().command is _tell
