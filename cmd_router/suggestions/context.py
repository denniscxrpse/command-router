#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ["lazy_suggest_srv_ctx"]

import threading
from typing import Final, final

from cmd_router.utils import log, uctx


@final
class _LazySuggestionsServerContext:
    """Shared runtime state for the lazy suggestions' server.

    Holds the configured ``address``/``port`` (writable through
    ``FixturesSetup.suggestions_server_address``/``suggestions_server_port``)
    plus the latest suggestion list produced by a ``POST`` request.

    The suggestion list is guarded by an internal lock because the HTTP
    server serves each request on its own handler instance (and, once
    threaded, on its own thread) while ``POST`` writers and ``GET`` readers
    may overlap. All accessors copy on the way in/out so callers can never
    mutate the stored list in place.
    """

    def __init__(self) -> None:
        self._address: str = uctx.SUGGESTION_SERVER_DEFAULT_ADDRESS
        self._port: int = uctx.SUGGESTION_SERVER_DEFAULT_PORT
        self._suggestions: list[str] = []
        self._last_input: str | None = None
        self._lock = threading.RLock()

    @property
    def address(self) -> str:
        """Return the configured bind address."""
        return self._address

    @address.setter
    def address(self, value: str) -> None:
        """Set the bind address, rejecting non-string values."""
        if not isinstance(value, str):
            log.error("invalid suggestions server address; expected str, got %s", type(value).__name__)
            raise TypeError(f"suggestions server address must be a str, got {type(value).__name__}")
        if not value:
            log.error("invalid suggestions server address; empty strings are not allowed")
            raise ValueError("suggestions server address must not be empty")
        self._address = value

    @property
    def port(self) -> int:
        """Return the configured bind port."""
        return self._port

    @port.setter
    def port(self, value: int) -> None:
        """Set the bind port, rejecting out-of-range values."""
        if not isinstance(value, int) or isinstance(value, bool):
            log.error("invalid suggestions server port; expected int, got %s", type(value).__name__)
            raise TypeError(f"suggestions server port must be an int, got {type(value).__name__}")
        if not 0 <= value <= 65535:
            log.error("invalid suggestions server port %r; expected 0-65535", value)
            raise ValueError("suggestions server port must be in range 0-65535")
        self._port = value

    def set_suggestions(self, suggestions: list[str], last_input: str | None = None) -> None:
        """Replace the stored suggestion list (copied) and remember its input.

        :raises TypeError: If *suggestions* is not a list of strings.
        """
        if not isinstance(suggestions, list) or not all(isinstance(item, str) for item in suggestions):
            log.error("invalid suggestions list; expected list[str], got %r", type(suggestions).__name__)
            raise TypeError(f"suggestions must be a list[str], got {type(suggestions).__name__}")
        with self._lock:
            self._suggestions = list(suggestions)
            self._last_input = last_input

    def get_suggestions(self) -> list[str]:
        """Return a copy of the stored suggestion list."""
        with self._lock:
            return list(self._suggestions)

    def clear(self) -> None:
        """Reset the stored suggestions and the remembered input."""
        with self._lock:
            self._suggestions = []
            self._last_input = None

    @property
    def last_input(self) -> str | None:
        """Return the input that produced the stored suggestions, if any."""
        with self._lock:
            return self._last_input


lazy_suggest_srv_ctx: Final[_LazySuggestionsServerContext] = _LazySuggestionsServerContext()
