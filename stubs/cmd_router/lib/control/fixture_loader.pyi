from pathlib import Path
from types import ModuleType

from cmd_router.utils import log as log

def _load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType: ...
