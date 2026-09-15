from pathlib import Path
from types import ModuleType

from pkg.utils import log as log

def _load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType: ...
