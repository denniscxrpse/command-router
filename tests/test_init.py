#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""`--init` scaffolding: copy bundled templates, refuse clobbering, explain `--genesis`.

The scaffold helper runs without booting the router; the two integration
cases below run `initialize` against a fresh router singleton, so the
shared production state is never touched.
"""

from importlib import resources
from pathlib import Path

import pytest

import command_router as command_router_module
from command_router import __CommandRouter, __Router
from command_router.utils.cli import flags
from command_router.utils.status import stat


def _template_files() -> set[str]:
    with resources.as_file(resources.files("command_router") / "_example" / "fixtures") as source:
        return {path.name for path in Path(source).iterdir() if path.name != "__pycache__"}


def test_scaffold_copies_templates_byte_identical(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    dest = tmp_path / "fresh"

    result = __CommandRouter()._scaffold(dest)

    assert result == stat.Success()
    assert {path.name for path in dest.iterdir()} == _template_files()
    with resources.as_file(resources.files("command_router") / "_example" / "fixtures" / "__init__.py") as expected:
        assert (dest / "__init__.py").read_bytes() == expected.read_bytes()
    out = capsys.readouterr().out
    assert "cmd-router --genesis" in out
    assert str(dest) in out


def test_scaffold_creates_missing_parents(tmp_path: Path) -> None:
    dest = tmp_path / "nested" / "deep" / "fixtures"

    assert __CommandRouter()._scaffold(dest) == stat.Success()
    assert (dest / "__init__.py").is_file()


def test_scaffold_refuses_non_empty_directory(tmp_path: Path) -> None:
    dest = tmp_path / "lived-in"
    dest.mkdir()
    (dest / "mine.txt").write_text("do not touch", encoding="utf-8")

    assert __CommandRouter()._scaffold(dest) == stat.Abort()
    assert (dest / "mine.txt").read_text(encoding="utf-8") == "do not touch"
    assert not (dest / "__init__.py").exists()


def test_scaffold_refuses_file_destination(tmp_path: Path) -> None:
    dest = tmp_path / "file"
    dest.write_text("not a directory", encoding="utf-8")

    assert __CommandRouter()._scaffold(dest) == stat.Abort()


def test_scaffold_none_targets_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert __CommandRouter()._scaffold(None) == stat.Success()
    assert (tmp_path / "fixtures" / "__init__.py").is_file()


@pytest.fixture
def _fresh_router(monkeypatch: pytest.MonkeyPatch) -> __CommandRouter:
    """Bind a fresh router singleton so `initialize` cannot touch shared state."""
    private = __Router()
    private.grammars = {}
    private.info = {}
    monkeypatch.setattr(command_router_module, "_router", private)
    return __CommandRouter()


def test_initialize_init_short_circuits_before_boot(
    _fresh_router: __CommandRouter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(flags, "init", tmp_path / "fresh")
    monkeypatch.setattr(flags, "verbose_help", None)

    result = _fresh_router.initialize

    assert result == stat.Success()
    assert (tmp_path / "fresh" / "__init__.py").is_file()
    assert _fresh_router._grammars == {}
    assert "Done. Run the program with" in capsys.readouterr().out


def test_initialize_verbose_help_short_circuits_before_boot(
    _fresh_router: __CommandRouter, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(flags, "verbose_help", "serve")
    monkeypatch.setattr(flags, "init", None)

    result = _fresh_router.initialize

    assert result == stat.Success()
    assert "Read dirty command lines" in capsys.readouterr().out


def test_initialize_verbose_help_unknown_name_aborts(
    _fresh_router: __CommandRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(flags, "verbose_help", "frobnicate")
    monkeypatch.setattr(flags, "init", None)

    assert _fresh_router.initialize == stat.Abort()
