#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Phase 7 public API: FixturesSDK single-class fixtures and sane Fixtures defaults."""

from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from cmd_router.lib.commands import CmdType
from cmd_router.lib.control import ControlType as Control
from cmd_router.sdk import (
    Fixtures,
    FixturesContextHolder,
    FixtureSettings,
    FixturesSDK,
    FixturesSetup,
    argument,
    build_dispatcher,
    literal,
    load_fixture_module,
)
from cmd_router.sdk.backend.settings import _FixtureInnerContext


class DemoSDK(FixturesSDK):
    def __init__(self) -> None:
        super().__init__()
        self.cmd_prefix = "/"
        self.command_action = {"say": self.say, "tell": self.say}

    def say(self, **arguments: Any) -> dict[str, Any]:
        return self._record("say", arguments)


def test_fixtures_has_sane_defaults() -> None:
    assert isinstance(Fixtures, FixturesSDK)
    assert Fixtures.cmd_prefix == "/"
    assert Fixtures.lazy_init_help is True
    assert Fixtures.command_action == {}
    assert Fixtures.command_args_ctrl == {}
    assert Fixtures.suggestions_get_size == 5
    assert Fixtures.calls == []
    assert Fixtures.logic is Fixtures


def test_user_api_binds_logic_to_self_and_records() -> None:
    api = DemoSDK()

    assert api.logic is api
    assert isinstance(api, FixturesContextHolder)
    assert isinstance(api, FixturesSetup)
    assert api.command_action["say"] == api.say
    assert api.say(message="hi") == {"message": "hi"}
    assert api.calls == [("say", {"message": "hi"})]
    assert FixturesSDK.ContextHolder is FixturesContextHolder
    assert FixturesSDK.Setup is FixturesSetup


def test_control_accepts_setup_instance_directly() -> None:
    api = DemoSDK()
    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>", "tell": "<target> <message...>"}, fixture=api)

        assert initialized.ok
        assert runner.deeper_context.fixture_module is None
        assert runner.deeper_context.fixture_logic is api
        assert runner.deeper_context.fixture_setup is api

        result = runner.execute("/say hello world")
        assert result.ok
        assert result.value == {"message": "hello world"}
        assert api.calls == [("say", {"message": "hello world"})]
    finally:
        runner.close()


def test_control_accepts_setup_subclass_directly() -> None:
    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=DemoSDK)

        assert initialized.ok
        assert isinstance(runner.deeper_context.fixture_setup, DemoSDK)
        assert runner.execute("/say hi").ok
    finally:
        runner.close()


def test_control_rejects_setup_without_logic() -> None:
    setup = FixturesSetup.__new__(FixturesSetup)
    FixtureSettings.__init__(setup)
    object.__setattr__(setup, "logic", None) if hasattr(setup, "__dict__") else setattr(setup, "logic", None)

    runner = Control()
    try:
        initialized = runner.initialize({"say": "<message...>"}, fixture=setup)

        assert not initialized.ok
        assert "fixture initialization failed" in initialized.message
    finally:
        runner.close()


def test_settings_parent_validates_like_legacy_setup() -> None:
    settings = FixtureSettings()

    with pytest.raises(TypeError, match="cmd_prefix must be a str"):
        settings.cmd_prefix = 1  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError, match="lazy_init_help must be a bool"):
        settings.lazy_init_help = "yes"  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError, match="command_action must be a dict"):
        settings.command_action = []  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError, match="command_args_ctrl must be a dict"):
        settings.command_args_ctrl = None  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError, match="must be a int"):
        settings.suggestions_set_current_size = "2"  # ty: ignore[invalid-assignment]
    with pytest.raises(ValueError, match=">="):
        settings.suggestions_set_current_size = -1


def test_setup_child_setting_drives_shared_suggestions_limit() -> None:
    _FixtureInnerContext.reset()
    FixturesContextHolder()
    setup = FixturesSetup(logic=object())
    setup.suggestions_set_current_size = 2

    assert FixturesSetup._resolve_suggestions_limit() == 2

    child_holder = FixturesContextHolder()
    assert child_holder is not None
    _FixtureInnerContext.reset()
    FixturesContextHolder()

    class Child(FixturesSetup):
        def __init__(self) -> None:
            super().__init__()
            self.suggestions_set_current_size = 2

    # Module path still publishes child settings to the shared global.
    module = ModuleType("api_child_fixture")
    module.context_holder = FixturesContextHolder  # ty: ignore[unresolved-attribute]
    module.SetupFixtures = Child  # ty: ignore[unresolved-attribute]
    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}, fixture=module).ok
        assert FixturesSetup._resolve_suggestions_limit() == 2
    finally:
        runner.close()


def test_backend_loader_delegates_for_paths(tmp_path: Path) -> None:
    target = tmp_path / "fix.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    first = load_fixture_module(target, 4242)
    second = load_fixture_module(target, 4242)

    assert first.VALUE == 1
    assert second.VALUE == 1

    with pytest.raises(TypeError, match="fixture must be"):
        load_fixture_module(123, 1)  # ty: ignore[invalid-argument-type]


def test_builder_and_control_compose_without_grammar_strings() -> None:
    api = DemoSDK()
    dispatcher = build_dispatcher(literal("say").then(argument("message", CmdType.greedy_string()).executes(api.say)))

    result = dispatcher.parse("say hello")
    assert result.ok
    assert result.handler == api.say
    assert result.context is not None
    assert result.context.args == {"message": "hello"}
