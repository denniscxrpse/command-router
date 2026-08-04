import asyncio
from types import ModuleType
from typing import Any

import pytest

from cmd_router.lib.control import Control
from cmd_router.utils.context import ctx
from cmd_router.utils.logger import log


@pytest.fixture
def clean_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctx, "cmd_prefix", "/")
    monkeypatch.setattr(ctx, "control_no_help_keeps_help", True)
    monkeypatch.setattr(ctx, "command_action", {})
    monkeypatch.setattr(ctx, "command_args_ctrl", {})


def test_control_returns_structured_results_and_keeps_deeper_state(clean_context: None) -> None:
    calls: list[dict[str, Any]] = []

    def say(**arguments: Any) -> dict[str, Any]:
        calls.append(arguments)
        return arguments

    ctx.command_action = {"say": say}
    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"})
        result = runner.execute("/say hello world")
        assert initialized.ok
        assert result.ok
        assert result.command == "say"
        assert result.parsed_args == {"message": "hello world"}
        assert result.value == {"message": "hello world"}
        assert result.to_dict()["parsed_args"] == {"message": "hello world"}
        assert calls == [{"message": "hello world"}]
        runner.deeper_level.command_action = {"say": lambda **arguments: {"replacement": arguments["message"]}}
        assert runner.execute("/say changed").value == {"replacement": "changed"}
        outside = runner.execute("ordinary input")
        assert outside.ok
        assert outside.kind == "input"
        assert runner.deeper_level.last_result is outside
        assert runner.deeper_level.dispatcher is not None
    finally:
        runner.close()


def test_fixture_initialization_only_calls_the_declared_hooks(clean_context: None) -> None:
    module = ModuleType("fixture_test")
    events: list[str] = []

    class Logic:
        def __init__(self) -> None:
            events.append("logic")

        def say(self, **arguments: Any) -> dict[str, Any]:
            return arguments

    def setup() -> None:
        events.append("setup")
        ctx.command_action = {"say": logic.say}

    logic = Logic.__new__(Logic)

    def make_logic() -> Logic:
        Logic.__init__(logic)
        return logic

    module.FixtureGrammarLogic = make_logic
    module.setup = setup

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=module)

        assert initialized.ok
        assert events == ["logic", "setup"]
        assert runner.deeper_level.fixture_module is module
        assert runner.deeper_level.fixture_logic is logic
        assert runner.execute("/say hello").value == {"message": "hello"}
    finally:
        runner.close()


def test_deeper_level_controls_arguments(clean_context: None) -> None:
    ctx.command_action = {"say": lambda **arguments: arguments}
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}).ok
        runner.deeper_level.set_command_args("say", message="controlled")

        assert runner.execute("/say original").value == {"message": "controlled"}
    finally:
        runner.close()


def test_help_can_be_disabled_and_async_actions_are_supported(clean_context: None) -> None:
    async def say(**arguments: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        return arguments

    ctx.command_action = {"say": say}
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}, keep_help=False).ok

        async def run() -> tuple[Any, Any]:
            return await runner.execute_async("/say hi"), await runner.execute_async("/help")

        command, help_result = asyncio.run(run())
        assert command.ok
        assert command.value == {"message": "hi"}
        assert not help_result.ok
        assert help_result.kind == "unexpected_token"
    finally:
        runner.close()


def test_stderr_writer_can_be_awaited(capsys: pytest.CaptureFixture[str]) -> None:
    async def write() -> None:
        await log.stderr("controlled stderr")

    asyncio.run(write())

    assert capsys.readouterr().err == "controlled stderr\n"
