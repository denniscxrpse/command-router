#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Phase 6 suggestions: size limits, flags, and dict-or-None error transport."""

import json

import pytest

from cmd_router.lib.commands import CmdParse
from cmd_router.lib.control import ControlType as Control
from cmd_router.lib.control.api import ControlResult
from cmd_router.lib.control.api.fittings import FixturesContextHolder, FixturesSetup
from cmd_router.lib.control.api.result import _UNSET
from cmd_router.utils.cli import flags
from cmd_router.utils.context import uctx
from cmd_router.utils.status import stat


def _make_error(expected: tuple[str, ...], token: str | None = None) -> CmdParse.Error:
    from cmd_router.lib.control.api.result import ControlResultKinds

    return CmdParse.Error(
        kind=ControlResultKinds.UNEXPECTED_TOKEN,
        token_index=0,
        expected=expected,
        message="unexpected",
        token=token,
    )


@pytest.fixture
def _clean_suggestion_state(monkeypatch: pytest.MonkeyPatch):
    """Isolate global suggestion flags and the shared setup size."""
    monkeypatch.setattr(flags, "no_suggestions", False)
    monkeypatch.setattr(flags, "max_sized_suggestions", False)
    monkeypatch.setattr(FixturesSetup, "_active_suggestions_size", None)
    # Ensure fresh defaults for resolvers that fall back when no setup exists.
    yield
    monkeypatch.setattr(FixturesSetup, "_active_suggestions_size", None)


def test_size_two_yields_first_two_words(_clean_suggestion_state) -> None:
    setup = FixturesSetup(logic=object())
    setup.suggestions_set_current_size = 2

    error = _make_error(("word1", "word2", "word3", "word4"))
    assert error._get_suggestions() == ["word1", "word2"]
    assert error.to_dict()["suggestions"] == ["word1", "word2"]

    result = ControlResult(
        ok=False,
        code=stat.Abort(),
        kind=error.kind,
        input="/unknown",
        error=error,
        message=error.message,
    )
    response = result.to_response()
    assert response["ok"] is False
    assert response["error"] is not None
    assert response["error"]["suggestions"] == ["word1", "word2"]
    assert response["suggestions"] == ["word1", "word2"]
    # Compact JSON keeps the fixed shape with nulls for absent values.
    parsed = json.loads(result.to_json(is_response=True))
    assert parsed["ok"] is False
    assert parsed["error"]["suggestions"] == ["word1", "word2"]


def test_default_size_truncates_to_five(_clean_suggestion_state) -> None:
    FixturesSetup(logic=object())

    error = _make_error(tuple(f"w{i}" for i in range(10)))
    assert error._get_suggestions() == [f"w{i}" for i in range(5)]


def test_no_suggestions_disables_both_layers(_clean_suggestion_state, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "no_suggestions", True)
    FixturesSetup(logic=object())

    error = _make_error(("word1", "word2"))
    assert error._get_suggestions() is None
    assert error.to_dict()["suggestions"] is None

    result = ControlResult(
        ok=False,
        code=stat.Abort(),
        kind=error.kind,
        input="/unknown",
        error=error,
        message="nope",
    )
    response = result.to_response()
    assert response["suggestions"] is None
    assert isinstance(response["error"], dict)
    assert response["error"]["suggestions"] is None


def test_max_sized_flag_forces_max_and_ignores_setter(_clean_suggestion_state, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "max_sized_suggestions", True)
    setup = FixturesSetup(logic=object())

    assert setup.suggestions_get_size == uctx.SUGGESTIONS_MAX
    assert FixturesSetup._resolve_suggestions_limit() == uctx.SUGGESTIONS_MAX

    # Setter is ignored while the flag is enabled.
    setup.suggestions_set_current_size = 2
    assert setup.suggestions_get_size == uctx.SUGGESTIONS_MAX

    # Best case: fewer candidates than MAX give up early.
    small = _make_error(("a", "b"))
    assert small._get_suggestions() == ["a", "b"]

    # Worst case: the byte budget truncates before SUGGESTIONS_MAX. Emission
    # stops once str(result) would exceed flags.suggestions_payload, so the
    # result is a pool-ordered prefix that fits the budget — never MAX items
    # of unbounded words.
    many = tuple(f"w{i}" for i in range(uctx.SUGGESTIONS_MAX + 50))
    large = _make_error(many)
    suggestions = large._get_suggestions()
    assert suggestions is not None
    assert len(suggestions) < uctx.SUGGESTIONS_MAX
    assert suggestions == list(many[: len(suggestions)])
    assert len(str(suggestions).encode("utf-8")) <= flags.suggestions_payload


def test_suggestions_setter_validates(_clean_suggestion_state) -> None:
    setup = FixturesSetup(logic=object())

    with pytest.raises(TypeError, match="must be a int"):
        setup.suggestions_set_current_size = "2"  # ty: ignore[invalid-assignment]

    with pytest.raises(ValueError, match="<="):
        setup.suggestions_set_current_size = uctx.SUGGESTIONS_MAX + 1

    with pytest.raises(ValueError, match=">= 0"):
        setup.suggestions_set_current_size = -1

    setup.suggestions_set_current_size = 0
    assert _make_error(("word1",))._get_suggestions() == []


def test_transport_value_is_always_dict_or_none(_clean_suggestion_state) -> None:
    assert ControlResult._transport_value(None) is None
    assert ControlResult._transport_value(_UNSET) is None

    error = _make_error(("word1", "word2"))
    transported = ControlResult._transport_value(error)
    assert isinstance(transported, dict)
    assert transported["suggestions"] == ["word1", "word2"][:5]

    payload = {"message": "custom", "suggestions": ["x"]}
    assert ControlResult._transport_value(payload) is payload

    wrapped_str = ControlResult._transport_value("boom")
    assert wrapped_str == {"message": "boom", "suggestions": []}

    wrapped_obj = ControlResult._transport_value(42)
    assert wrapped_obj == {"message": "42", "suggestions": []}


def test_transport_value_wraps_strings_as_none_when_disabled(
    _clean_suggestion_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(flags, "no_suggestions", True)
    assert ControlResult._transport_value("boom") == {"message": "boom", "suggestions": None}


def test_top_level_suggestions_mirror_error(_clean_suggestion_state) -> None:
    setup = FixturesSetup(logic=object())
    setup.suggestions_set_current_size = 2

    error = _make_error(("word1", "word2", "word3"))
    failed = ControlResult(
        ok=False,
        code=stat.Abort(),
        kind=error.kind,
        input="/x",
        error=error,
        message="bad",
    )
    assert failed.suggestions == ["word1", "word2"]

    succeeded = ControlResult(
        ok=True,
        code=stat.Success(),
        kind=failed.kind,
        input="/say hi",
        value={"message": "hi"},
    )
    assert succeeded.suggestions == []
    assert succeeded.to_response()["error"] is None


def test_control_unknown_command_respects_size_two(_clean_suggestion_state) -> None:
    setup = FixturesSetup(logic=object())
    setup.suggestions_set_current_size = 2

    runner = Control()
    try:
        runner.deeper_context.command_action = {"say": lambda **arguments: arguments}
        assert runner.initialize({"say": "<message...>", "tell": "<target> <message...>"}).ok

        # Use size from the test setup for the control's active setup as well.
        runner.deeper_context.setup.suggestions_set_current_size = 2
        # "/unknown" has no prefix or close fuzzy match, so ranking correctly
        # returns [] instead of the whole pool.
        failed = runner.execute("/unknown")

        assert not failed.ok
        assert failed.error is not None
        response = failed.to_response()
        assert isinstance(response["error"], dict)
        assert response["error"]["suggestions"] == response["suggestions"] == []
        json.loads(failed.to_json(is_response=True))
        json.loads(failed.to_dict()["error"] and json.dumps(failed.to_dict()))
    finally:
        runner.close()


def test_advanc_suggests_advancement_only(_clean_suggestion_state) -> None:
    FixturesSetup(logic=object())

    runner = Control()
    try:
        runner.deeper_context.command_action = {
            name: (lambda **arguments: arguments) for name in ("say", "tell", "gamemode", "advancement")
        }
        assert runner.initialize(
            {
                "say": "<message...>",
                "tell": "<target> <message...>",
                "gamemode": "(survival|creative)",
                "advancement": "<target>",
            }
        ).ok

        failed = runner.execute("/advanc")
        assert not failed.ok
        response = failed.to_response()
        assert response["suggestions"] == ["advancement"]
        assert response["error"]["suggestions"] == ["advancement"]
        assert "tell" not in response["suggestions"]
    finally:
        runner.close()


def test_gamemod_suggests_gamemode_only(_clean_suggestion_state) -> None:
    FixturesSetup(logic=object())

    runner = Control()
    try:
        runner.deeper_context.command_action = {
            name: (lambda **arguments: arguments) for name in ("say", "tell", "gamemode", "advancement")
        }
        assert runner.initialize(
            {
                "say": "<message...>",
                "tell": "<target> <message...>",
                "gamemode": "(survival|creative)",
                "advancement": "<target>",
            }
        ).ok

        failed = runner.execute("/gamemod")
        assert not failed.ok
        response = failed.to_response()
        # Closest is gamemode; tell/say/help must not sneak in.
        assert response["suggestions"] == ["gamemode"]
        assert response["error"]["suggestions"] == ["gamemode"]
    finally:
        runner.close()


def test_prefix_narrowing_beats_registration_order(_clean_suggestion_state) -> None:
    FixturesSetup(logic=object())
    # Same pool in registration order, different fragments rank differently.
    assert _make_error(("gamemode", "tell", "advancement", "say", "help"), token="advanc")._get_suggestions() == [
        "advancement"
    ]
    assert _make_error(("gamemode", "tell", "advancement", "say", "help"), token="gamemod")._get_suggestions() == [
        "gamemode"
    ]
    # No close match -> empty, not the whole pool.
    assert _make_error(("gamemode", "tell", "advancement", "say", "help"), token="unknown")._get_suggestions() == []


def test_fuzzy_fallback_for_typos(_clean_suggestion_state) -> None:
    FixturesSetup(logic=object())
    # "tlel" shares no prefix with "tell" but is within distance 2.
    assert _make_error(("say", "tell", "help"), token="tlel")._get_suggestions() == ["tell"]
    # Far drift is capped, like git/npm did-you-mean.
    assert _make_error(("say", "tell", "help"), token="zzz")._get_suggestions() == []


def test_incomplete_input_returns_hints_in_order(_clean_suggestion_state) -> None:
    FixturesSetup(logic=object())
    setup = FixturesSetup(logic=object())
    setup.suggestions_set_current_size = 2
    # token None means incomplete: no fragment to rank, return pool slice.
    assert _make_error(("word1", "word2", "word3"), token=None)._get_suggestions() == ["word1", "word2"]


def test_fixture_child_setting_drives_suggestions(_clean_suggestion_state) -> None:
    class Holder(FixturesContextHolder):
        pass

    class ChildSetup(FixturesSetup):
        def __init__(self) -> None:
            super().__init__()
            self.suggestions_set_current_size = 2

    from types import ModuleType

    module = ModuleType("suggestion_fixture")
    # ty: ignore[unresolved-attribute]
    module.context_holder = Holder
    # ty: ignore[unresolved-attribute]
    module.SetupFixtures = ChildSetup

    runner = Control()
    try:
        assert runner.initialize({"say": "<message...>"}, fixture=module).ok
        failed = runner.execute("/unknown")
        assert failed.to_response()["error"]["suggestions"] is not None
        assert len(failed.to_response()["suggestions"]) <= 2
    finally:
        runner.close()
