#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParseError:
    """The furthest failure encountered while traversing the command tree."""

    kind: str
    token_index: int
    expected: tuple[str, ...] = ()
    message: str = ""
    partial_args: dict[str, Any] = field(default_factory=dict)
    code: int | None = None

    @property
    def position(self) -> int:
        """Alias for the token index at which parsing stopped."""
        return self.token_index

    @property
    def expectations(self) -> tuple[str, ...]:
        """Alias useful to callers that prefer the noun form."""
        return self.expected
