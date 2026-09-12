from pathlib import Path
from types import ModuleType

__all__ = ["load_fixture_module"]

def load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType: ...
