#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Serve mode: dirty stdin lines in, one JSON response per stderr line."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from cmd_router.utils.cli import flags, init_flags

ROOT = Path(__file__).resolve().parents[1]

DIRTY = [
    "/say hello world",
    "  /tell Alex \"hi there\"  ",
    "/gamemode creative",
    "/bogus )))",
    "/tell",
    "",
    "just some text",
    "/say \"unterminated",
]


def _serve(lines: list[str], timeout: int = 180) -> tuple[list[dict[str, Any]], int, str]:
    """Run `main.py --serve` as a child; return stderr responses, exit code, and stdout."""
    proc = subprocess.Popen(
        [sys.executable, "main.py", "--serve"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate("\n".join(lines) + "\n", timeout=timeout)
    return [json.loads(line) for line in err.splitlines()], proc.returncode, out


def test_serve_option_updates_environment_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "serve", False)

    result = CliRunner().invoke(init_flags, ["--serve"])

    assert result.exit_code == 0
    assert flags.serve is True


def test_serve_answers_every_dirty_line_with_one_json_response() -> None:
    responses, returncode, _ = _serve(DIRTY)

    assert returncode == 0
    assert len(responses) == len(DIRTY)
    assert [response["input"] for response in responses] == DIRTY


def test_serve_responses_keep_the_fixed_contract_shape() -> None:
    responses, _, _ = _serve(DIRTY)

    for response in responses:
        assert set(response) == {
            "ok",
            "code",
            "kind",
            "input",
            "command",
            "value",
            "parsed_args",
            "error",
            "message",
            "exception",
        }


def test_serve_covers_success_passthrough_and_failure() -> None:
    responses, _, _ = _serve(DIRTY)
    by_input = {response["input"]: response for response in responses}

    assert by_input["/say hello world"]["ok"] is True
    assert by_input["/say hello world"]["value"] == {"message": "hello world"}

    assert by_input[""]["ok"] is True
    assert by_input[""]["value"] == ""
    assert by_input["just some text"]["ok"] is True

    assert by_input["/tell"]["ok"] is False
    assert by_input["/tell"]["error"]["expected"] == ["<target>"]

    assert by_input['/say "unterminated']["ok"] is False
    assert by_input['/say "unterminated']["error"]["kind"] == "TOKENIZATION"


def test_serve_keeps_protocol_lines_off_stdout() -> None:
    _, _, out = _serve(DIRTY)

    assert out.splitlines() != []
    assert all(not line.startswith('{"ok"') for line in out.splitlines())
