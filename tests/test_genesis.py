#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Genesis flag: custom fixture directories outside the bundled tree."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from command_router import __Router
from command_router.utils.cli import flags, init_flags

ROOT = Path(__file__).resolve().parents[1]

_FIXTURE_INIT = """\
from typing import Any

from command_router.sdk import FixturesSDK


class Fixtures(FixturesSDK):
    def __init__(self, logic: Any = None) -> None:
        super().__init__(logic=logic)
        self.cmd_prefix = "/"
        self.lazy_init_help = False
        self.command_action = {"ping": self.logic.ping}

    def ping(self, **arguments: Any) -> dict[str, Any]:
        return {"pong": True, **arguments}
"""

_GRAMMAR_TOML = """\
[cmd-router]
schema-version = 1

[cmd-router.grammar]
ping = "<message...>"
"""


def _make_genesis(root: Path, *, with_init: bool = True) -> Path:
    """Create an outside-scope genesis directory with a grammar and optional fixture."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "custom.toml").write_text(_GRAMMAR_TOML, encoding="utf-8")
    if with_init:
        (root / "__init__.py").write_text(_FIXTURE_INIT, encoding="utf-8")
    return root


def test_genesis_option_keeps_path_type(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(flags, "genesis", None)

    result = CliRunner().invoke(init_flags, ["--genesis", str(tmp_path)])

    assert result.exit_code == 0
    assert isinstance(flags.genesis, Path)
    assert flags.genesis == tmp_path


def test_genesis_source_unset_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "genesis", None)

    assert __Router().genesis_source is None


def test_genesis_source_missing_directory_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(flags, "genesis", tmp_path / "absent")

    assert __Router().genesis_source is None


def test_genesis_source_without_init_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    genesis = _make_genesis(tmp_path / "noinit", with_init=False)
    monkeypatch.setattr(flags, "genesis", genesis)

    assert __Router().genesis_source is None


def test_genesis_source_valid_directory_returns_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    genesis = _make_genesis(tmp_path / "custom")
    monkeypatch.setattr(flags, "genesis", genesis)

    assert __Router().genesis_source == genesis


def test_genesis_source_coerces_programmatic_strings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    genesis = _make_genesis(tmp_path / "custom")
    monkeypatch.setattr(flags, "genesis", str(genesis))

    assert __Router().genesis_source == genesis


def _child_env() -> dict[str, str]:
    """Point the child at the source tree so `-m command_router` resolves without an install."""
    return {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def _serve_genesis(genesis: Path, lines: list[str], timeout: int = 180) -> tuple[str, str, int]:
    """Run `cmd-router --genesis <dir> --serve` as a child; return stdout, stderr, and exit code."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "command_router", "--genesis", str(genesis), "--serve"],
        cwd=ROOT,
        env=_child_env(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate("\n".join(lines) + "\n", timeout=timeout)
    return out, err, proc.returncode


def test_genesis_uses_custom_grammars_and_fixture(tmp_path: Path) -> None:
    genesis = _make_genesis(tmp_path / "custom")

    _, err, returncode = _serve_genesis(genesis, ["/ping hello", "/say hi"])
    responses = [json.loads(line) for line in err.splitlines()]

    assert returncode == 0
    assert len(responses) == 2
    assert responses[0]["ok"] is True
    assert responses[0]["command"] == "ping"
    assert responses[0]["value"] == {"pong": True, "message": "hello"}
    assert responses[1]["ok"] is False
    assert responses[1]["command"] == "say"


def test_genesis_missing_directory_fails_without_traceback(tmp_path: Path) -> None:
    out, err, returncode = _serve_genesis(tmp_path / "absent", ["/ping hello"])

    assert returncode != 0
    assert "Traceback" not in out + err


def test_genesis_without_init_fails_without_traceback(tmp_path: Path) -> None:
    genesis = _make_genesis(tmp_path / "noinit", with_init=False)

    out, err, returncode = _serve_genesis(genesis, ["/ping hello"])

    assert returncode != 0
    assert "Traceback" not in out + err
