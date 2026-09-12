#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

import pytest
from click.testing import CliRunner

from cmd_router.utils.cli import flags, init_flags


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
