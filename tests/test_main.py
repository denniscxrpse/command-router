#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Importable entry point: `main(entry)` initializes flags without `sys.argv`.

These tests stay on failure-fast paths on purpose. A successful `main`
run would normalize grammars into the shared router singleton, attach a
fixture to the shared control surface, and bind the suggestions server,
so success paths are proven by the subprocess suites instead
(`test_serve.py`, `test_genesis.py`). Every case here restores the
process-global flags and stdout rendering it touches.
"""

import pytest

import main as entrypoint
from pkg.utils.cli import flags
from pkg.utils.logger import log_handler
from pkg.utils.status import stat


@pytest.fixture
def _isolated_process_state():
    """Snapshot global flags and stdout rendering; restore both afterwards."""
    saved = dict(flags.__dict__)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(flags, name, value)
        log_handler.set_stdout_enabled(True)


def test_main_entry_parses_flags_before_starting(_isolated_process_state) -> None:
    result = entrypoint.main(("--quiet", "--no-help", "--genesis", "/absent-dir"))

    assert result == stat.Abort()
    assert flags.quiet is True
    assert flags.no_help is True


def test_main_entry_invalid_option_raises_before_routing(_isolated_process_state) -> None:
    with pytest.raises(SystemExit):
        entrypoint.main(("--bogus-flag",))

    assert flags.quiet is False


def test_main_absent_entry_leaves_flags_alone(_isolated_process_state, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flags, "genesis", "/absent-dir")

    result = entrypoint.main()

    assert result == stat.Abort()
    assert flags.genesis == "/absent-dir"
