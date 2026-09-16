#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from command_router.utils.cli import (
    _BARE_OPTION_DEFAULTS,
    _help,
    _init,
    _quiet,
    _verbose_help,
    cli_flags,
    describe_flags,
    flag_names,
    flags,
    init_flags,
    normalize_bare_options,
)
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


@pytest.mark.parametrize("option", ["-i", "--init"])
def test_init_option_accepts_all_spellings(option: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(flags, "init", None)

    result = CliRunner().invoke(init_flags, [option, str(tmp_path / "fresh")])

    assert result.exit_code == 0
    assert flags.init == tmp_path / "fresh"


def test_init_short_flag_stays_distinct_from_ignore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(flags, "init", None)
    monkeypatch.setattr(flags, "ignore", flags.ignore)

    result = CliRunner().invoke(init_flags, ["-i", str(tmp_path / "fresh"), "-I", "x.json5"])

    assert result.exit_code == 0
    assert flags.init == tmp_path / "fresh"
    assert flags.ignore == frozenset({"x.json5"})


@pytest.mark.parametrize("option", ["-H", "--verbose-help"])
def test_verbose_help_option_accepts_both_spellings(option: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "verbose_help", None)

    result = CliRunner().invoke(init_flags, [option, "serve"])

    assert result.exit_code == 0
    assert flags.verbose_help == "serve"


def test_help_flag_does_not_trigger_verbose_help(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "verbose_help", None)

    result = CliRunner().invoke(init_flags, ["-h"])

    assert result.exit_code == 0
    assert flags.verbose_help is None


def test_bare_defaults_derive_from_alias_lists() -> None:
    assert set(_BARE_OPTION_DEFAULTS) == set(_init) | set(_verbose_help)
    assert _BARE_OPTION_DEFAULTS["--init"] == "fixtures"
    assert _BARE_OPTION_DEFAULTS["--verbose-help"] == "all"


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("quiet", ("-q", "--quiet")),
        ("help", ("-h", "--help")),
        ("verbose_help", ("-H", "--verbose-help")),
        ("serve", ("--serve",)),
        ("genesis", ("--genesis",)),
    ],
)
def test_cli_flags_reports_parser_spellings(field: str, expected: tuple[str, ...]) -> None:
    assert cli_flags(field) == expected


def test_cli_flags_agrees_with_alias_lists() -> None:
    assert set(cli_flags("init")) == set(_init)
    assert set(cli_flags("verbose_help")) == set(_verbose_help)
    assert set(cli_flags("help")) == set(_help)
    assert set(cli_flags("quiet")) == set(_quiet)


def test_cli_flags_rejects_unknown_names() -> None:
    with pytest.raises(ValueError, match="unknown flag"):
        cli_flags("frobnicate")


ROOT = Path(__file__).resolve().parents[1]


def _child_env() -> dict[str, str]:
    """Point the child at the source tree so `-m command_router` resolves without an install."""
    return {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def test_help_output_stays_free_of_import_logs() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "command_router", "--help"],
        cwd=ROOT,
        env=_child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, _ = proc.communicate(timeout=120)

    assert proc.returncode == 0
    assert "Usage:" in out
    assert all(not line.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")) for line in out.splitlines())


def test_quiet_output_stays_free_of_logs() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "command_router", "--quiet", "--verbose-help", "quiet"],
        cwd=ROOT,
        env=_child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, _ = proc.communicate(timeout=120)

    assert proc.returncode == 0
    assert "quiet: bool" in out
    assert all(not line.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")) for line in out.splitlines())


def test_help_stays_clean_when_imports_log(tmp_path: Path) -> None:
    # Shadow `rapidfuzz` with a failing module so `suggestions.algo` emits
    # its import-time fallback error; `--help` must still print clean help
    # because the log handler silences itself on early help tokens.
    shadow = tmp_path / "rapidfuzz"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise ImportError('shadowed for test')\n")
    env = {**_child_env(), "PYTHONPATH": f"{tmp_path}{os.pathsep}{ROOT / 'src'}"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "command_router", "--help"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, _ = proc.communicate(timeout=120)

    assert proc.returncode == 0
    assert "Usage:" in out
    assert all(not line.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")) for line in out.splitlines())


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
        (["-i"], ["-i", "fixtures"]),
        (["-H"], ["-H", "all"]),
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
