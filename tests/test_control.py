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
from cmd_router.lib.control.api.result import _UNSET
from cmd_router.utils.logger import log
from cmd_router.utils.status import stat


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
    import ast
    import json

    from cmd_router.utils.context import uctx

    runner = Control()
    try:
        runner.deeper_context.command_action = {"tell": lambda **arguments: arguments}
        assert runner.initialize({"tell": "<target> <message...>"}).ok

        failed = runner.execute("/tell Alex")
        failure_output = capsys.readouterr().err
        assert failed.value is _UNSET
        assert failed.error_payload is failed.error
        assert failed.error is not None
        assert failed.error.partial_args == {"target": "Alex"}
        assert "'data'" not in failure_output
        assert "'kind': 'UNEXPECTED_COMMAND'" in failure_output
        assert "'partial_args': {'target': 'Alex'}" in failure_output

        failure_response = ast.literal_eval(failure_output.strip())
        assert set(failure_response) == set(uctx.INTERNAL_JSON_CONTRACT_COMPACT)
        assert failure_response["ok"] is False
        assert failure_response["input"] == "/tell Alex"
        assert failure_response["value"] is None
        assert failure_response["message"] == "expected one of: <message...>"

        failure_dict = failed.to_dict()
        assert set(failure_dict) == set(uctx.INTERNAL_JSON_CONTRACT)
        assert failure_dict["ok"] is False
        assert failure_dict["command"] == "tell"
        assert failure_dict["value"] is None
        assert failure_dict["parsed_args"] is None
        assert failure_dict["error"] is not None
        assert failure_dict["message"] == "expected one of: <message...>"
        assert failure_dict["exception"] is None
        json.dumps(failure_dict)
        json.dumps(failure_response)

        succeeded = runner.execute("/tell Alex hello")
        assert succeeded.value == {"target": "Alex", "message": "hello"}
        assert succeeded.error_payload is None
        success_output = capsys.readouterr().err
        success_response = ast.literal_eval(success_output.strip())
        assert set(success_response) == set(uctx.INTERNAL_JSON_CONTRACT_COMPACT)
        assert success_response == {
            "ok": True,
            "input": "/tell Alex hello",
            "value": {"target": "Alex", "message": "hello"},
            "suggestions": [],
            "error": None,
            "message": None,
        }

        success_dict = succeeded.to_dict()
        assert set(success_dict) == set(uctx.INTERNAL_JSON_CONTRACT)
        assert success_dict["message"] is None
        assert success_dict["exception"] is None
        assert success_dict["error"] is None
        assert success_dict["parsed_args"] == {"target": "Alex", "message": "hello"}
        json.dumps(success_dict)
        json.dumps(success_response)
    finally:
        runner.close()


def test_control_result_preserves_explicit_data_and_error_payloads() -> None:
    fallback = {"message": "custom failure", "suggestions": []}
    kind = ControlResultKinds.COMMAND
    # noinspection unresolved-references
    kind.custom = "custom"
    result = api.ControlResult(True, stat.Success(), kind.custom, None, value={"answer": 42}, error_payload=fallback)

    assert isinstance(result.kind, ControlResultKinds)
    assert result.kind.value == "custom"
    assert result.value == {"answer": 42}
    assert result.error_payload is fallback
    # Dict payloads are already dict|null shaped, so transport preserves them.
    assert result.to_response() == {
        "ok": True,
        "input": None,
        "value": {"answer": 42},
        "suggestions": [],
        "error": fallback,
        "message": None,
    }


def test_control_result_wraps_arbitrary_error_payload_as_dict() -> None:
    fallback = object()
    kind = ControlResultKinds.COMMAND
    result = api.ControlResult(True, stat.Success(), kind, None, value={"answer": 42}, error_payload=fallback)

    assert result.error_payload is fallback
    transported = result.to_response()["error"]
    assert isinstance(transported, dict)
    assert transported == {"message": str(fallback), "suggestions": []}


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

    # ty: ignore[unresolved-attribute]
    module.context_holder = Logic
    # ty: ignore[unresolved-attribute]
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
    assert api.Api.Surface.get_latest_stderr() == "controlled stderr\n"


def test_fixture_inner_context_flags_track_holder_and_setup_lifecycle() -> None:
    """Verify the holder/setup flags flip after each ``__init__`` runs."""
    _FixtureInnerContext.reset()

    assert _FixtureInnerContext.did_context_holder_ever_initialize is False
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is False

    FixturesContextHolder()
    assert _FixtureInnerContext.did_context_holder_ever_initialize is True
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is False

    FixturesSetup(logic=object())
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is True


def test_fixture_inner_context_validate_raises_when_holder_did_not_finish() -> None:
    """``validate()`` reports a missing holder even when the setup succeeded."""
    _FixtureInnerContext.reset()
    FixturesSetup(logic=object())

    result = _FixtureInnerContext.validate()
    assert isinstance(result, FixtureInitializationError)
    assert "FixturesContextHolder did not finish initialization" in result.message


def test_fixture_inner_context_validate_raises_when_setup_did_not_finish() -> None:
    """``validate()`` reports a missing setup once the holder is recorded."""
    _FixtureInnerContext.reset()
    FixturesContextHolder()

    result = _FixtureInnerContext.validate()
    assert isinstance(result, FixtureInitializationError)
    assert "FixturesSetup did not finish initialization" in result.message


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
    assert _FixtureInnerContext.did_context_holder_ever_initialize is False
    assert _FixtureInnerContext.did_fixture_setup_ever_initialize is False

    result = _FixtureInnerContext.validate()
    assert isinstance(result, FixtureInitializationError)
    assert "FixturesContextHolder did not finish initialization" in result.message


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

    module = ModuleType("bad_holder_fixture")
    # ty: ignore[unresolved-attribute]
    module.context_holder = BadHolder
    # ty: ignore[unresolved-attribute]
    module.SetupFixtures = GoodSetup

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=module)

        assert not initialized.ok
        assert initialized.code.name == stat.FixtureInitializationError().name
        assert initialized.message == "fixture initialization failed"
        assert initialized.exception is None
        assert "FixturesContextHolder did not finish initialization" in initialized.code.message
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

    module = ModuleType("bad_setup_fixture")
    # ty: ignore[unresolved-attribute]
    module.context_holder = GoodHolder
    # ty: ignore[unresolved-attribute]
    module.SetupFixtures = BadSetup

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=module)

        assert not initialized.ok
        assert initialized.code.name == stat.FixtureInitializationError().name
        assert initialized.message == "fixture initialization failed"
        assert initialized.exception is None
        assert "FixturesSetup did not finish initialization" in initialized.code.message
        assert runner.deeper_context.fixture_module is None
    finally:
        runner.close()
