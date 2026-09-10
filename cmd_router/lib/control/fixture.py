#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Resolve control fixture sources into executable Python modules.

Control fixtures may be supplied as an already-imported ``ModuleType``, as a
normal import name, or as a filesystem path to a Python module/package.  This
module deliberately handles only that source-resolution and execution step.
It does not inspect the fixture for ``context_holder`` or ``SetupFixtures``;
the higher-level control API performs that lifecycle validation and constructs
the holder/setup pair in the required order.

Source resolution follows a small, predictable rule set:

* A ``ModuleType`` is returned unchanged.  No new module name is created and
  no code is executed.
* A ``Path`` is always treated as a filesystem location.  A string is first
  interpreted as a path.  If that path does not exist and the string does not
  end with ``.py``, the string is treated as an import name and passed to
  ``importlib.import_module``.  A missing string ending in ``.py`` is kept on
  the path branch so the caller receives a useful ``FileNotFoundError``.
* A directory source is resolved to its ``__init__.py`` file.  A file source
  must exist and be a regular file before a module spec is requested.

File-backed fixtures are loaded with ``importlib.util.spec_from_file_location``
under a generated private name of the form
``_cmd_router_fixture_<identifier>``.  The module is placed in
``sys.modules`` before ``exec_module`` runs, matching the important part of
normal import behavior and allowing code executed by the fixture to resolve
its own generated module entry.  Successful loads remain in ``sys.modules``
for the lifetime of the process.  If execution raises, the temporary entry is
removed and the original exception is re-raised; callers can therefore see the
real fixture failure without leaving a partially initialized module behind.

The loader does not modify ``sys.path``, cache modules by their source path,
or sandbox fixture code.  Loading a file executes arbitrary Python from that
file, including its import-time side effects.  The caller normally supplies a
stable per-control identifier (``Control`` uses ``id(self)``) so concurrently
loaded fixtures do not overwrite one another's generated names.  Invalid
source types, missing files, and unsupported import/spec situations are
reported with ordinary ``TypeError``, ``FileNotFoundError``, or ``ImportError``
exceptions; the control API converts them into a structured fixture
initialization result.

The public entry point of this implementation module is private by design:
normal callers should pass ``fixture=...`` to ``Control.initialize``.
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from cmd_router.utils import log


def _load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType:
    """Load and return a fixture module from an object, import name, or path.

    An existing module object is returned as-is.  For a string, an existing
    path wins; otherwise a string without a ``.py`` suffix is interpreted as a
    module import name.  Files and directories are loaded from the disk using a
    generated module name based on *identifier*.  Directories use their
    ``__init__.py`` file, which lets a fixture package retain the normal
    package-style spec created by ``spec_from_file_location``.

    The generated module is inserted into ``sys.modules`` before execution, so
    import-time code sees the same registration invariant as a normal import.
    If execution fails, only that generated entry is removed and the original
    exception is allowed to propagate.  A successful file load is intentionally
    left registered; this keeps the returned module importable by its generated
    name for the rest of the process.  This function does not call fixture
    hooks or validate their presence.

    :param source: Module object, importable module name, Python file path, or
        directory containing ``__init__.py``.
    :param identifier: Value used to form the generated private module name.
        The function does not validate or otherwise transform it.
    :raises TypeError: If *source* is not a supported source kind.
    :raises FileNotFoundError: If a path source does not resolve to a file.
    :raises ImportError: If Python cannot create a usable file-module spec.
    :return: The existing module or the newly executed file-backed module.
    """
    log.debug("resolving source %r", source)
    if isinstance(source, ModuleType):
        log.warning("using existing module %s", source.__name__)
        return source

    if isinstance(source, Path):
        candidate = source
    elif isinstance(source, str):
        candidate = Path(source)
        if not candidate.exists() and not source.endswith(".py"):
            log.debug("importing module by name %r", source)
            try:
                module = importlib.import_module(source)
            except Exception as exception:
                log.critical("module import failed: %s", exception)
                raise
            log.debug("imported module %s", module.__name__)
            return module
    else:
        raise TypeError("fixture must be a module, module name, or path")

    if candidate.is_dir():
        log.debug("resolving package directory %s", candidate)
        candidate = candidate / "__init__.py"
    if not candidate.is_file():
        log.critical("fixture file does not exist: %s", candidate)
        raise FileNotFoundError(f"fixture module does not exist: {candidate}")

    module_name = f"_cmd_router_fixture_{identifier}"
    log.debug("loading %s as %s", candidate, module_name)
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        log.critical("could not create an import spec for %s", candidate)
        raise ImportError(f"could not load fixture module: {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exception:
        sys.modules.pop(module_name, None)
        log.critical("execution of %s failed: %s", candidate, exception)
        if isinstance(exception, AttributeError):
            log.debug(
                "AttributeError loading '%s'. if using `cmd_router.fittings`, verify "
                "dataclass attributes are correctly assigned and not overridden. "
                "this may indicate a logic error rather than an implementation bug.",
                candidate.name,
            )
        raise
    log.info("loaded fixture %s", candidate)
    return module
