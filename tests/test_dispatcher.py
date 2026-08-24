from collections.abc import Callable
from typing import Any

import pytest

from cmd_router.lib.command import CmdError, CmdNode, CmdParse, CmdType


def say_handler() -> None:
    return None


def tell_handler() -> None:
    return None


def gamemode_handler() -> None:
    return None


def advancement_handler() -> None:
    return None


def tp_handler() -> None:
    return None


def debug_handler() -> None:
    return None


def _phase_one_dispatcher() -> tuple[CmdNode.Dispatcher, dict[str, Callable[..., Any]]]:
    handlers: dict[str, Callable[..., Any]] = {
        "say": say_handler,
        "tell": tell_handler,
        "gamemode": gamemode_handler,
        "advancement": advancement_handler,
        "tp": tp_handler,
        "debug": debug_handler,
    }
    dispatcher = CmdNode.Dispatcher()

    say = CmdNode.Literal("say")
    say.add_child(CmdNode.Argument("message", CmdType.GreedyString(), command=handlers["say"]))
    dispatcher.register(say)

    tell = CmdNode.Literal("tell")
    tell_target = CmdNode.Argument("target", CmdType.Word())
    tell_target.add_child(CmdNode.Argument("message", CmdType.GreedyString(), command=handlers["tell"]))
    tell.add_child(tell_target)
    dispatcher.register(tell)

    gamemode = CmdNode.Literal("gamemode")
    for mode in ("survival", "creative", "adventure", "spectator"):
        mode_node = CmdNode.Literal(mode, command=handlers["gamemode"])
        mode_node.add_child(CmdNode.Argument("target", CmdType.Word(), command=handlers["gamemode"]))
        gamemode.add_child(mode_node)
    dispatcher.register(gamemode)

    advancement = CmdNode.Literal("advancement")
    for action in ("grant", "revoke"):
        action_node = CmdNode.Literal(action)
        target_node = CmdNode.Argument("target", CmdType.Word())
        target_node.add_child(CmdNode.Literal("*", command=handlers["advancement"]))

        only_node = CmdNode.Literal("only")
        advancement_node = CmdNode.Argument("advancement", CmdType.Word(), command=handlers["advancement"])
        advancement_node.add_child(CmdNode.Argument("criterion", CmdType.Word(), command=handlers["advancement"]))
        only_node.add_child(advancement_node)

        target_node.add_child(only_node)
        action_node.add_child(target_node)
        advancement.add_child(action_node)
    dispatcher.register(advancement)

    tp = CmdNode.Literal("tp")
    x_node = CmdNode.Argument("x", CmdType.Int())
    y_node = CmdNode.Argument("y", CmdType.Int())
    y_node.add_child(CmdNode.Argument("z", CmdType.Int(), command=handlers["tp"]))
    x_node.add_child(y_node)
    tp.add_child(x_node)
    dispatcher.register(tp)

    debug = CmdNode.Literal("debug")
    debug.add_child(CmdNode.Literal("on", command=handlers["debug"]))
    debug.add_child(CmdNode.Literal("off", command=handlers["debug"]))
    dispatcher.register(debug)

    return dispatcher, handlers


@pytest.mark.parametrize(
    ("command", "handler_name", "expected_args"),
    [
        ("say hello world", "say", {"message": "hello world"}),
        ('tell Alex "hello world"', "tell", {"target": "Alex", "message": "hello world"}),
        ("gamemode creative", "gamemode", {}),
        ("gamemode spectator Alex", "gamemode", {"target": "Alex"}),
        ("advancement grant Alex *", "advancement", {"target": "Alex"}),
        ("advancement revoke Alex only story", "advancement", {"target": "Alex", "advancement": "story"}),
        (
            'advancement grant Alex only story "done"',
            "advancement",
            {"target": "Alex", "advancement": "story", "criterion": "done"},
        ),
        ("tp 10 -2 3", "tp", {"x": 10, "y": -2, "z": 3}),
        ("debug off", "debug", {}),
    ],
)
def test_phase_one_commands_parse_to_handlers_and_context(
    command: str, handler_name: str, expected_args: dict[str, Any]
) -> None:
    dispatcher, handlers = _phase_one_dispatcher()

    result = dispatcher.parse(command)

    assert result.ok
    assert result.handler is handlers[handler_name]
    assert result.context is not None
    assert result.context.original_input == command
    assert result.context.parsed_args == expected_args
    assert result.context.cursor == len(result.context.tokens)


@pytest.mark.parametrize(
    ("command", "kind", "token_index", "expected"),
    [
        (
            "gamemode hardcore",
            "unexpected_token",
            1,
            ("survival", "creative", "adventure", "spectator"),
        ),
        ("tell Alex", "incomplete_command", 2, ("<message...>",)),
        ("advancement grant Alex only", "incomplete_command", 4, ("<advancement>",)),
        ("tp 1 nope 3", "invalid_argument", 2, ("<y:int>",)),
    ],
)
def test_phase_one_failures_report_the_furthest_expectation(
    command: str, kind: str, token_index: int, expected: tuple[str, ...]
) -> None:
    dispatcher, _ = _phase_one_dispatcher()

    result = dispatcher.parse(command)

    assert not result.ok
    assert result.error is not None
    assert result.error.kind == kind
    assert result.error.token_index == token_index
    assert result.error.expected == expected


def test_dispatcher_returns_tokenization_error_codes() -> None:
    dispatcher, _ = _phase_one_dispatcher()

    result = dispatcher.parse('say "unterminated')

    assert not result.ok
    assert result.error is not None
    assert result.error.kind == "tokenization"
    assert result.error.code == CmdError.TokenizeInvalidError


def test_parse_error_exposes_failure_context_for_debugging() -> None:
    dispatcher, _ = _phase_one_dispatcher()

    result = dispatcher.parse("tell Alex")

    assert result.error is not None
    assert result.error.position == 2
    assert result.error.cursor == 2
    assert result.error.expectations == ("<message...>",)
    assert result.error.parsed_args == {"target": "Alex"}
    assert result.error.to_dict() == {
        "kind": "incomplete_command",
        "token_index": 2,
        "expected": ("<message...>",),
        "message": "expected one of: <message...>",
        "partial_args": {"target": "Alex"},
        "code": None,
    }


def test_literal_branches_take_precedence_over_argument_branches() -> None:
    def literal_handler() -> None:
        return None

    def argument_handler() -> None:
        return None

    root = CmdNode.Literal("root")
    root.add_child(CmdNode.Literal("known", command=literal_handler))
    root.add_child(CmdNode.Argument("value", CmdType.Word(), command=argument_handler))
    dispatcher = CmdNode.Dispatcher()
    dispatcher.register(root)

    literal_result = dispatcher.parse("root known")
    argument_result = dispatcher.parse("root other")

    assert literal_result.handler is literal_handler
    assert argument_result.handler is argument_handler
    assert argument_result.context is not None
    assert argument_result.context.args == {"value": "other"}


def test_greedy_arguments_must_be_terminal() -> None:
    greedy = CmdNode.Argument("message", CmdType.GreedyString())

    with pytest.raises(ValueError, match="greedy argument nodes must be terminal"):
        greedy.add_child(CmdNode.Literal("later"))


def test_empty_input_reports_root_expectations() -> None:
    dispatcher, _ = _phase_one_dispatcher()

    result = dispatcher.parse("   ")

    assert isinstance(result, CmdParse.Result)
    assert not result.ok
    assert result.error is not None
    assert result.error.kind == "incomplete_command"
    assert result.error.token_index == 0
    assert result.error.expected == ("say", "tell", "gamemode", "advancement", "tp", "debug")


def test_command_namespaces_expose_concise_aliases() -> None:
    assert CmdError.ArgumentParseError.__name__ == "ArgumentParseError"
    assert issubclass(CmdType.Int, CmdType.ArgumentType)
    assert CmdParse.Error.__name__ == "ParseError"
    assert CmdParse.Result.__name__ == "ParseResult"
    assert CmdNode.Root.__name__ == "RootNode"
    assert CmdNode.Literal.__name__ == "LiteralNode"
    # pyrefly: ignore [bad-argument-type]
    assert CmdNode.Argument("value", CmdType.Int).argument_type.name == "int"
