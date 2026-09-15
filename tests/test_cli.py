#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from pathlib import Path

import pytest
from click.testing import CliRunner

from command_router.utils.cli import describe_flags, flag_names, flags, init_flags, normalize_bare_options
from command_router.utils.logger import log_handler


def test_cli_options_update_renamed_environment_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "test_suite", False)
    monkeypatch.setattr(flags, "no_help", False)
    monkeypatch.setattr(flags, "no_suggestions", True)

    result = CliRunner().invoke(init_flags, ["-test", "--no-help", "--no-suggestions"])

    assert result.exit_code == 0
    assert flags.test_suite is True
    assert flags.no_help is True
    assert flags.no_suggestions is True


@pytest.mark.parametrize("option", ["-I", "--ignore"])
def test_ignore_option_updates_environment_flag(option: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "ignore", flags.ignore)

    result = CliRunner().invoke(init_flags, [option, "grammars.json5", option, "grammars.toml"])

    assert result.exit_code == 0
    assert flags.ignore == frozenset({"grammars.json5", "grammars.toml"})


@pytest.mark.parametrize("option", ["-q", "--quiet"])
def test_quiet_option_updates_environment_flag(option: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "quiet", False)

    try:
        result = CliRunner().invoke(init_flags, [option])

        assert result.exit_code == 0
        assert flags.quiet is True
    finally:
        log_handler.set_stdout_enabled(True)


def test_quiet_option_suspends_stdout_rendering(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "quiet", False)
    log_handler.set_stdout_enabled(True)

    try:
        result = CliRunner().invoke(init_flags, ["--quiet"])

        assert result.exit_code == 0
        assert log_handler.stdout_enabled is False
    finally:
        log_handler.set_stdout_enabled(True)

    assert log_handler.stdout_enabled is True


def test_init_flags_without_quiet_restores_stdout_rendering() -> None:
    log_handler.set_stdout_enabled(False)

    try:
        result = CliRunner().invoke(init_flags, [])

        assert result.exit_code == 0
        assert log_handler.stdout_enabled is True
    finally:
        log_handler.set_stdout_enabled(True)


@pytest.mark.parametrize("option", ["-init", "--init"])
def test_init_option_accepts_both_spellings(option: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(flags, "init", None)

    result = CliRunner().invoke(init_flags, [option, str(tmp_path / "fresh")])

    assert result.exit_code == 0
    assert flags.init == tmp_path / "fresh"


def test_init_option_requires_a_value() -> None:
    # Stock click cannot express an option that is valid both bare and
    # valued, which is why `start` expands bare occurrences beforehand.
    result = CliRunner().invoke(init_flags, ["--init"])

    assert result.exit_code == 2


def test_verbose_help_option_takes_an_optional_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "verbose_help", None)

    result = CliRunner().invoke(init_flags, ["--verbose-help", "serve"])

    assert result.exit_code == 0
    assert flags.verbose_help == "serve"


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], []),
        (["--init"], ["--init", "fixtures"]),
        (["-init"], ["-init", "fixtures"]),
        (["--init", "mydir"], ["--init", "mydir"]),
        (["--init", "--serve"], ["--init", "fixtures", "--serve"]),
        (["--init=mydir"], ["--init=mydir"]),
        (["--init", "-weird"], ["--init", "fixtures", "-weird"]),
        (["--verbose-help"], ["--verbose-help", "all"]),
        (["--verbose-help", "serve"], ["--verbose-help", "serve"]),
        (["--serve", "--", "--init"], ["--serve", "--", "--init"]),
    ],
)
def test_normalize_bare_options_expands_exact_tokens(args: list[str], expected: list[str]) -> None:
    assert normalize_bare_options(args) == expected


def test_flag_names_covers_verbose_and_init() -> None:
    assert "verbose_help" in flag_names()
    assert "init" in flag_names()


def test_describe_flags_reports_live_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "quiet", True)

    text = describe_flags("quiet")

    assert text == "quiet: bool (default False, current True)"


def test_describe_flags_all_covers_every_flag() -> None:
    lines = describe_flags("all").splitlines()

    assert [line.split(":")[0] for line in lines] == list(flag_names())


def test_describe_flags_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="unknown flag"):
        describe_flags("frobnicate")
