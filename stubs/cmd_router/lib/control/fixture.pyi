from cmd_router.utils.logger import log as log
from pathlib import Path
from types import ModuleType

def _load_fixture_module(source: ModuleType | str | Path, identifier: int) -> ModuleType: ...
