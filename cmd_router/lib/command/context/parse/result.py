#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# We normally don't import like this, but since everything is encapsulated, it's fine.
from . import CommandContext
from .err import ParseError

_Handler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ParseResult:
    """Either a handler/context pair or a structured parse failure."""

    handler: _Handler | None = None
    context: CommandContext | None = None
    error: ParseError | None = None

    @property
    def ok(self) -> bool:
        """Whether parsing reached a node with a handler."""
        return self.handler is not None and self.context is not None and self.error is None

    @property
    def success(self) -> bool:
        """Readable alias for :attr:`ok`."""
        return self.ok
