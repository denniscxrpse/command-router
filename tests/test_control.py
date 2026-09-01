import asyncio
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from cmd_router.lib.control import ControlResultKinds, FixturesContextHolder, FixturesSetup, api
from cmd_router.lib.control import ControlType as Control
from cmd_router.lib.control.api.fittings import (
    FixtureInitializationError,
    _FixtureInnerContext,
)
from cmd_router.utils.context import error
from cmd_router.utils.logger import log


def test_control_returns_structured_results_and_keeps_deeper_state() -> None:
    calls: list[dict[str, Any]] = []

    def say(**arguments: Any) -> dict[str, Any]:
        calls.append(arguments)
        return arguments

    runner = Control()
    try:
        runner.deeper_context.command_action = {"say": say}
        initialized = runner.initialize({"say": "<message...>"})
        result = runner.execute("/say hello world")
        assert initialized.ok
        assert result.ok
        assert result.command == "say"
        assert result.parsed_args == {"message": "hello world"}
        assert result.value == {"message": "hello world"}
        assert result.to_dict()["parsed_args"] == {"message": "hello world"}
        assert calls == [{"message": "hello world"}]
        runner.deeper_context.command_action = {"say": lambda **arguments: {"replacement": arguments["message"]}}
        assert runner.execute("/say changed").value == {"replacement": "changed"}
        outside = runner.execute("ordinary input")
        assert outside.ok
        assert outside.kind == ControlResultKinds.INPUT
        assert runner.deeper_context.last_result is outside
        assert runner.deeper_context.dispatcher is not None
    finally:
        runner.close()


def test_control_emits_compact_data_and_error_responses_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    runner = Control()
    try:
        runner.deeper_context.command_action = {"tell": lambda **arguments: arguments}
        assert runner.initialize({"tell": "<target> <message...>"}).ok

        failed = runner.execute("/tell Alex")
        failure_output = capsys.readouterr().err
        assert failed.data is None
        assert failed.error_payload is failed.error
        assert failed.error is not None
        assert failed.error.partial_args == {"target": "Alex"}
        assert "'data': None" in failure_output
        # noinspection string-conversion-without-dunder-method
        assert f"'err': {{'kind': {ControlResultKinds.UNEXPECTED_COMMAND!r}" in failure_output
        assert "'partial_args': {'target': 'Alex'}" in failure_output

        succeeded = runner.execute("/tell Alex hello")
        assert succeeded.data == {"target": "Alex", "message": "hello"}
        assert succeeded.error_payload is None
        assert capsys.readouterr().err == (
            "{'data': {'target': 'Alex', 'message': 'hello'}, 'err': None, 'suggestions': []}\n"
        )
    finally:
        runner.close()


def test_control_result_preserves_explicit_data_and_error_payloads() -> None:
    fallback = object()
    kind = ControlResultKinds.COMMAND
    # noinspection unresolved-references
    kind.custom = "custom"
    result = api.ControlResult(True, 0, kind.custom, None, data={"answer": 42}, error_payload=fallback)

    assert isinstance(result.kind, ControlResultKinds)
    assert result.kind.value == "custom"
    assert result.data == {"answer": 42}
    assert result.error_payload is fallback
    assert result.to_response() == {"data": result.data, "err": fallback, "suggestions": []}


def test_builtin_help_lists_commands_and_searches_a_specific_command() -> None:
    runner = Control()
    try:
        runner.deeper_context.command_action = {
            "say": lambda **arguments: arguments,
            "tell": lambda **arguments: arguments,
        }
        initialized = runner.initialize({"say": "<message...>", "tell": "<target> <message...>"})

        overview = runner.execute("/help")
        assert initialized.ok
        assert overview.ok
        assert overview.value == {
            "commands": ("say", "tell"),
            "prefix": "/",
            "target": None,
        }

        specific = runner.execute("/help tell")
        assert specific.ok
        assert specific.parsed_args == {"target": "tell"}
        assert specific.value == {
            "commands": ("say", "tell"),
            "prefix": "/",
            "target": 'tell = "<target> <message...>"',
        }

        missing = runner.execute("/help missing")
        assert missing.ok
        assert missing.parsed_args == {"target": "missing"}
        assert missing.value["target"] is None
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
        assert runner.deeper_context.fixture_module is module
        assert isinstance(runner.deeper_context.fixture_logic, Logic)
        assert isinstance(runner.deeper_context.fixture_setup, Setup)
        assert runner.execute("/say hello").value == {"message": "hello"}
    finally:
        runner.close()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    (
        ("cmd_prefix", 1, "cmd_prefix must be a str, got int"),
        (
            "lazy_init_help",
            "yes",
            "lazy_init_help must be a bool, got str",
        ),
        ("command_action", [], "command_action must be a dict, got list"),
        ("command_args_ctrl", None, "command_args_ctrl must be a dict, got NoneType"),
    ),
)
def test_fixture_setup_type_errors_name_the_property(name: str, value: Any, message: str) -> None:
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
        assert runner.deeper_context.fixture_logic.calls == [("bar", {"message": "hello"})]
    finally:
        runner.close()


def test_deeper_level_controls_arguments() -> None:
    runner = Control()
    try:
        runner.deeper_context.command_action = {"say": lambda **arguments: arguments}
        assert runner.initialize({"say": "<message...>"}).ok
        runner.deeper_context.set_command_args("say", message="controlled")

        assert runner.execute("/say original").value == {"message": "controlled"}
    finally:
        runner.close()


def test_help_can_be_disabled_and_async_actions_are_supported() -> None:
    async def say(**arguments: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        return arguments

    runner = Control()
    try:
        runner.deeper_context.command_action = {"say": say}
        assert runner.initialize({"say": "<message...>"}, keep_help=False).ok

        async def run() -> tuple[Any, Any]:
            return await runner.execute_async("/say hi"), await runner.execute_async("/help")

        command, help_result = asyncio.run(run())
        assert command.ok
        assert command.value == {"message": "hi"}
        assert not help_result.ok
        assert help_result.kind == ControlResultKinds.UNEXPECTED_TOKEN
    finally:
        runner.close()


def test_stderr_writer_can_be_awaited(capsys: pytest.CaptureFixture[str]) -> None:
    async def write() -> None:
        await log.stderr("controlled stderr")

    asyncio.run(write())

    assert capsys.readouterr().err == "controlled stderr\n"
    assert log.stderr.latest_call == "controlled stderr\n"
    assert api.surface.listener() == "controlled stderr\n"


def test_fixture_inner_context_flags_track_holder_and_setup_lifecycle() -> None:
    """Verify the holder/setup flags flip after each ``__init__`` runs."""
    _FixtureInnerContext.reset()

    assert _FixtureInnerContext.did_context_holder_ever_initialize is False
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is False

    FixturesContextHolder()
    assert _FixtureInnerContext.did_context_holder_ever_initialize is True  # pyrefly: ignore [unnecessary-comparison]
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is False  # pyrefly: ignore [unnecessary-comparison]

    FixturesSetup(logic=object())
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is True  # pyrefly: ignore [unnecessary-comparison]


def test_fixture_inner_context_validate_raises_when_holder_did_not_finish() -> None:
    """``validate()`` reports a missing holder even when the setup succeeded."""
    _FixtureInnerContext.reset()
    FixturesSetup(logic=object())

    with pytest.raises(FixtureInitializationError, match="FixturesContextHolder did not finish initialization"):
        _FixtureInnerContext.validate()


def test_fixture_inner_context_validate_raises_when_setup_did_not_finish() -> None:
    """``validate()`` reports a missing setup once the holder is recorded."""
    _FixtureInnerContext.reset()
    FixturesContextHolder()

    with pytest.raises(FixtureInitializationError, match="FixturesSetup did not finish initialization"):
        _FixtureInnerContext.validate()


def test_fixture_inner_context_validate_passes_when_both_flags_are_set() -> None:
    """``validate()`` returns silently once both ``__init__``s have run."""
    _FixtureInnerContext.reset()
    FixturesContextHolder()
    FixturesSetup(logic=object())

    _FixtureInnerContext.validate()


def test_fixture_inner_context_reset_clears_stale_flags() -> None:
    """A stale flag from a prior setup must not mask a missing holder init."""
    FixturesContextHolder()
    FixturesSetup(logic=object())
    assert _FixtureInnerContext.did_context_holder_ever_initialize is True

    _FixtureInnerContext.reset()
    assert _FixtureInnerContext.did_context_holder_ever_initialize is False  # pyrefly: ignore [unnecessary-comparison]
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is False

    with pytest.raises(FixtureInitializationError, match="FixturesContextHolder did not finish initialization"):
        _FixtureInnerContext.validate()


def test_control_reports_control_fixture_error_when_holder_skips_super() -> None:
    """A fixture whose holder omits ``super().__init__()`` fails the control init."""

    # noinspection missing-constructor
    class BadHolder(FixturesContextHolder):
        def __init__(self) -> None:
            pass

    class GoodSetup(FixturesSetup):
        def __init__(self) -> None:
            super().__init__(logic=object())
            self.command_action = {"say": lambda **arguments: arguments}

    # pyrefly: ignore [missing-attribute]
    module = ModuleType("bad_holder_fixture")
    # pyrefly: ignore [missing-attribute]
    module.context_holder = BadHolder
    # pyrefly: ignore [missing-attribute]
    module.SetupFixtures = GoodSetup

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=module)

        assert not initialized.ok
        assert initialized.code == error.ControlFixtureError
        assert initialized.message == "fixture initialization failed"
        assert initialized.exception is not None
        assert "FixtureInitializationError" in initialized.exception
        assert "FixturesContextHolder did not finish initialization" in initialized.exception
        assert runner.deeper_context.fixture_module is None
    finally:
        runner.close()


def test_control_reports_control_fixture_error_when_setup_skips_super() -> None:
    """A fixture whose setup omits ``super().__init__()`` fails the control init."""

    class GoodHolder(FixturesContextHolder):
        def __init__(self) -> None:
            super().__init__()

    # noinspection missing-constructor
    class BadSetup(FixturesSetup):
        logic: Any = None

        def __init__(self) -> None:
            pass

    # pyrefly: ignore [missing-attribute]
    module = ModuleType("bad_setup_fixture")
    # pyrefly: ignore [missing-attribute]
    module.context_holder = GoodHolder
    # pyrefly: ignore [missing-attribute]
    module.SetupFixtures = BadSetup

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=module)

        assert not initialized.ok
        assert initialized.code == error.ControlFixtureError
        assert initialized.message == "fixture initialization failed"
        assert initialized.exception is not None
        assert "FixtureInitializationError" in initialized.exception
        assert "FixturesSetup did not finish initialization" in initialized.exception
        assert runner.deeper_context.fixture_module is None
    finally:
        runner.close()
