import asyncio
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from cmd_router.lib.control import Control, FixturesContextHolder, FixturesSetup
from cmd_router.utils.logger import log


def test_control_returns_structured_results_and_keeps_deeper_state() -> None:
    calls: list[dict[str, Any]] = []

    def say(**arguments: Any) -> dict[str, Any]:
        calls.append(arguments)
        return arguments

    runner = Control()
    try:
        runner.deeper_level.command_action = {"say": say}
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


def test_fixture_initialization_creates_holder_then_setup() -> None:
    module = ModuleType("fixture_test")
    events: list[str] = []

    class Logic(FixturesContextHolder):
        def __init__(self) -> None:
            super().__init__()
            events.append("logic")

        @staticmethod
        def say(**arguments: Any) -> dict[str, Any]:
            return arguments

    class Setup(FixturesSetup):
        def __init__(self) -> None:
            super().__init__()
            events.append("setup")
            self.command_action = {"say": self.logic.say}

    # pyrefly: ignore [missing-attribute]
    module.context_holder = Logic
    # pyrefly: ignore [missing-attribute]
    module.SetupFixtures = Setup

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=module)

        assert initialized.ok
        assert events == ["logic", "setup"]
        assert runner.deeper_level.fixture_module is module
        assert isinstance(runner.deeper_level.fixture_logic, Logic)
        assert isinstance(runner.deeper_level.fixture_setup, Setup)
        assert runner.execute("/say hello").value == {"message": "hello"}
    finally:
        runner.close()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        ("cmd_prefix", 1, "cmd_prefix must be a str, got int"),
        (
            "control_no_help_keeps_help",
            "yes",
            "control_no_help_keeps_help must be a bool, got str",
        ),
        ("command_action", [], "command_action must be a dict, got list"),
        ("command_args_ctrl", None, "command_args_ctrl must be a dict, got NoneType"),
    ),
)
def test_fixture_setup_type_errors_name_the_property(
    name: str, value: Any, message: str
) -> None:
    setup = FixturesSetup(logic=object())

    with pytest.raises(TypeError, match=message):
        setattr(setup, name, value)


def test_bundled_fixture_uses_the_new_setup_contract() -> None:
    runner = Control()
    try:
        fixture = Path(__file__).parents[1] / "fixtures"
        initialized = runner.initialize({"say": "<message...>"}, fixture=fixture)

        assert initialized.ok
        result = runner.execute("/say hello")
        assert result.ok
        assert result.value == {"message": "hello"}
        assert runner.deeper_level.fixture_logic.calls == [("bar", {"message": "hello"})]
    finally:
        runner.close()


def test_deeper_level_controls_arguments() -> None:
    runner = Control()
    try:
        runner.deeper_level.command_action = {"say": lambda **arguments: arguments}
        assert runner.initialize({"say": "<message...>"}).ok
        runner.deeper_level.set_command_args("say", message="controlled")

        assert runner.execute("/say original").value == {"message": "controlled"}
    finally:
        runner.close()


def test_help_can_be_disabled_and_async_actions_are_supported() -> None:
    async def say(**arguments: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        return arguments

    runner = Control()
    try:
        runner.deeper_level.command_action = {"say": say}
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
