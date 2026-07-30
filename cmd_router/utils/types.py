from pathlib import Path
from typing import Any

# Commons
DictMapping = dict[str, Any]
OptionalMapping = DictMapping | int

# Specials
LogicalDataPath = Path | str | None
