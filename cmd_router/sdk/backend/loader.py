#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Resolve fixture sources into executable Python modules.

This is the ``cmd_router.sdk`` entry point for the source-resolution step.
For module names, file paths, and already-imported modules it delegates to
the long-standing loader in ``cmd_router.lib.control.fixture_loader`` so
there is exactly one implementation of path-vs.-import disambiguation,
package ``__init__.py`` handling, generated private module names, and
``sys.modules`` registration/cleanup.  Fixture *instances* (``FixturesSDK`` /
layer attaches them directly instead of calling this module.

``FixturesSetup`` objects) intentionally bypass module loading; the control
Supported sources for `load_fixture_module`:

- an already-imported ``ModuleType`` (returned unchanged),
- an importable module name,
- a file or directory path (directories resolve to ``__init__.py``).

``identifier`` only seeds the generated private name
(``_cmd_router_fixture_<identifier>``) for file-backed loads.  Callers
normally pass ``id(control)`` so concurrent controls do not overwrite each
other.  Loading executes arbitrary Python from the file, including
import-time side effects.  Invalid sources surface as ``TypeError``,
``FileNotFoundError``, or ``ImportError``; the control API converts those
into a structured fixture-initialization result.
"""

from pathlib import Path
from types import ModuleType

from cmd_router.lib.control.fixture_loader import _load_fixture_module as _legacy_load
from cmd_router.utils import log

__all__ = ("load_fixture_module",)


def load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType:
    """Load and return a fixture module from an object, import name, or path.

    This is a thin, documented façade over the control loader.  Behavior,
    naming, ``sys.modules`` handling, and error types are inherited
    unchanged; see ``cmd_router.lib.control.fixture_loader`` for the full
    contract.

    :param source: Module object, importable name, file path, or directory
        containing ``__init__.py``.
    :param identifier: Seed for the generated private module name.
    :return: The existing module or the newly executed file-backed module.
    """
    log.debug("sdk backend resolving fixture source %r", source)
    return _legacy_load(source, identifier)
