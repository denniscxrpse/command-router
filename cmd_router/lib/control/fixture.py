#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Load fixture modules for control initialization."""

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType:
    """Load a fixture module from an object, name, or path."""
    if isinstance(source, ModuleType):
        return source

    if isinstance(source, Path):
        candidate = source
    elif isinstance(source, str):
        candidate = Path(source)
        if not candidate.exists() and not source.endswith(".py"):
            return importlib.import_module(source)
    else:
        raise TypeError("fixture must be a module, module name, or path")

    if candidate.is_dir():
        candidate = candidate / "__init__.py"
    if not candidate.is_file():
        raise FileNotFoundError(f"fixture module does not exist: {candidate}")

    module_name = f"_cmd_router_fixture_{identifier}"
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load fixture module: {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module
