#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandContext:
    """The input and arguments captured by a successful parse."""

    input: str
    args: dict[str, Any]
    cursor: int
    tokens: tuple[str, ...]

    @property
    def original_input(self) -> str:
        """Return the complete command string used for parsing."""
        return self.input

    @property
    def parsed_args(self) -> dict[str, Any]:
        """Return the arguments captured along the successful path."""
        return self.args

    def get(self, name: str, default: Any = None) -> Any:
        """Read a named argument without exposing a ``KeyError``."""
        return self.args.get(name, default)
