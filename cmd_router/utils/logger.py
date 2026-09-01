#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = (
    "log_handler",
    "log",
)

import logging as _log
import sys
from collections.abc import Awaitable
from datetime import datetime
from html import escape
from threading import RLock
from types import FrameType
from typing import Any, Final, TextIO, final

from prompt_toolkit import HTML, print_formatted_text

_LOGGER_GLOBALS = globals()
_PROJECT_PACKAGE_PREFIX = "cmd_router."

_end = "\n"


class _CompletedWrite:
    """An awaitable that is already complete.

    ``log.stderr`` remains usable by synchronous code, while callers that are
    already asynchronous may also write ``await log.stderr(...)``. The writing
    happens before this object is returned, so old call sites do not leave an
    un-awaited coroutine behind.
    """

    def __await__(self):
        if False:
            yield None
        return None


class _LockedStderr:
    """Serialize writes to a stream shared by embedded commands runners."""

    def __init__(self, stream: TextIO, lock: RLock) -> None:
        self._stream = stream
        self._lock = lock

    def write(self, text: str) -> int:
        with self._lock:
            return self._stream.write(text)

    def flush(self) -> None:
        with self._lock:
            self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class _StderrWriter:
    """Callable stderr writer supporting async callers and latest-call observation."""

    def __init__(self, lock: RLock) -> None:
        self._lock = lock
        self.__latest: str = ""

    @property
    def _latest(self) -> str:
        """Read the latest emitted message while holding the stderr lock."""
        with self._lock:
            return self.__latest

    @_latest.setter
    def _latest(self, v: str) -> None:
        """Store the latest emitted message for this writer."""
        with self._lock:
            self.__latest = v

    def __call__(self, *message: Any, sep: str = " ", end: str = _end) -> Awaitable[None]:
        text: str = sep.join(str(arg) for arg in message) + end
        with self._lock:
            self._latest = text
            print(text, sep="", end="", file=sys.stderr, flush=True)
        return _CompletedWrite()

    async def async_write(self, *message: Any, sep: str = " ", end: str = _end) -> None:
        self(*message, sep=sep, end=end)

    @property
    def latest_call(self) -> str:
        """Return the most recent message emitted by this writer."""
        return self._latest


@final
class LoggerHandler:
    def __init__(self) -> None:
        """Render application logs to stdout with a consistent level style.

        The ordinary log methods are intentionally stdout-only.  ``stderr`` and
        ``stderr_async`` are separate listener/protocol writers and must not be
        used as an alternate error channel.
        """
        self.logger = _log.getLogger(__name__)
        self.logger.setLevel(_log.DEBUG)
        self._colors: dict[int, str] = {
            _log.DEBUG: "#45fcff",  # Light cyan
            _log.INFO: "#7bd88f",  # Light green
            _log.WARNING: "#ff9900",  # Orange
            _log.ERROR: "#fc618d",  # Pinkish-red
            _log.CRITICAL: "#800024",  # Dark red
        }

        self.log_id = datetime.now().strftime("%m-%d-%Y.%H:%M:%S")
        self._stdout_lock = RLock()
        self._stderr_lock = RLock()
        self._stderr_proxy: _LockedStderr | None = None
        self._stderr_original: TextIO | None = None
        self._stderr_users = 0
        # paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def lock_stderr(self) -> None:
        """Route direct stderr writes through the same process-wide lock."""
        if self._stderr_proxy is not None:
            self._stderr_users += 1
            return
        self._stderr_original = sys.stderr
        self._stderr_proxy = _LockedStderr(sys.stderr, self._stderr_lock)
        self._stderr_users = 1
        sys.stderr = self._stderr_proxy

    def unlock_stderr(self) -> None:
        """Restore stderr if this handler previously wrapped it."""
        if self._stderr_proxy is None:
            return
        self._stderr_users -= 1
        if self._stderr_users > 0:
            return
        if sys.stderr is self._stderr_proxy and self._stderr_original is not None:
            sys.stderr = self._stderr_original
        self._stderr_proxy = None
        self._stderr_original = None
        self._stderr_users = 0

    @staticmethod
    def get_final_message(level: int, message: str) -> dict[str, str]:
        """
        Returns:

        - "logl" -> log_level
        - "time" -> timestamp
        - "msg" -> final_message
        - "fmsg" -> Well-formatted string with timestamp and final_message.
        """
        # If this causes a crash, is the developer's fault.
        log_level = _log.getLevelName(level)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_message = f"{log_level} - {message}"
        return {
            "logl": log_level,
            "time": timestamp,
            "msg": final_message,
            "fmsg": f"{timestamp} - {final_message}",
        }

    def html(self, msg: str, level: int = _log.INFO) -> HTML:
        """Helper: Returns a formatted HTML message. Uses log levels to format the color quicker."""
        color = self._colors.get(level, "#291f1c")
        return HTML(f'<style fg="{color}">{escape(msg)}</style>')

    def log(self, level: int, *message: Any, sep: str, end: str) -> None:
        """Write a colored, timestamped level message to stdout.

        Calls remain print-like when no format marker is present.  A message
        containing ``%s``/``%r``-style markers may pass values separately,
        which keeps diagnostics readable without requiring every call site to
        build an eager string.
        """
        m = self._format_message(message, sep)
        final_message = self.get_final_message(level, m + end)

        with self._stdout_lock:
            print_formatted_text(
                self.html(final_message["msg"], level),
                sep="",
                end="",
                file=sys.stdout,
                flush=True,
            )

    def raw(self, *message: Any, sep: str, end: str) -> None:
        """Write an unadorned progress/status message to stdout.

        Unlike ``log``, this method does not add a timestamp or level.  It
        is useful for a two-part status such as ``"grammar: "`` followed by
        ``"OK"`` or ``"FAILURE"``.

        Separators and final characters still apply to the formatting.  The
        message is not escaped because this helper is intended for controlled
        status text rather than arbitrary user input.
        """
        m: str = sep.join(str(arg) for arg in message)
        final_message = m + end
        with self._stdout_lock:
            print_formatted_text(HTML(final_message), sep="", end="", file=sys.stdout, flush=True)

    @staticmethod
    def _format_message(message: tuple[Any, ...], sep: str) -> str:
        """Format logger arguments with caller information and optional %-style formatting.

        This method walks the call stack to identify the original caller (skipping
        internal logger frames), prepends the caller's qualified name to the message,
        and supports print-like variadic arguments as well as %-style formatting.

        Args:
            message: Tuple of arguments to format into a log message.
            sep: Separator string to join multiple message arguments.

        Returns:
            Formatted string in the form "LEVEL - caller: formatted_message", where
            the caller's module prefix is stripped if it matches the project package.
            If the first argument contains % markers and additional arguments are
            provided, attempts %-style formatting; falls back to sep-joined output
            if formatting fails.
        """

        # noinspection protected-member
        frame: FrameType | None = sys._getframe(1)
        while frame is not None and frame.f_globals is _LOGGER_GLOBALS:
            frame = frame.f_back

        if frame is None:
            caller = "<unknown>"
        else:
            module_name = frame.f_globals.get("__name__", "")
            qualname = frame.f_code.co_qualname
            if qualname == "<module>":
                caller = module_name or "<unknown>"
            elif module_name:
                caller = f"{module_name}.{qualname}"
            else:
                caller = qualname

        caller = caller.replace(_PROJECT_PACKAGE_PREFIX, "")

        if len(message) > 1 and isinstance(message[0], str) and "%" in message[0]:
            try:
                return f"{caller}: {message[0] % tuple(message[1:])}"
            except TypeError, ValueError:
                # A malformed diagnostic should still be visible rather than
                # raising a second exception while reporting the first one.
                pass
        return f"{caller}: {sep.join(str(arg) for arg in message)}"


log_handler = LoggerHandler()


class Logger:
    """``LoggerHandler`` wrapper with a consistent API."""

    @staticmethod
    def debug(*message: Any, sep=" ", end=_end) -> None:
        log_handler.log(_log.DEBUG, *message, sep=sep, end=end)

    @staticmethod
    def info(*message: Any, sep=" ", end=_end) -> None:
        log_handler.log(_log.INFO, *message, sep=sep, end=end)

    @staticmethod
    def warning(*message: Any, sep=" ", end=_end) -> None:
        log_handler.log(_log.WARNING, *message, sep=sep, end=end)

    @staticmethod
    def error(*message: Any, sep=" ", end=_end) -> None:
        log_handler.log(_log.ERROR, *message, sep=sep, end=end)

    @staticmethod
    def critical(*message: Any, sep=" ", end=_end) -> None:
        log_handler.log(_log.CRITICAL, *message, sep=sep, end=end)

    @staticmethod
    def raw(*message: Any, sep=" ", end=_end) -> None:
        log_handler.raw(*message, sep=sep, end=end)

    # noinspection protected-member
    stderr: Final[_StderrWriter] = _StderrWriter(log_handler._stderr_lock)

    @staticmethod
    async def stderr_async(*message: Any, sep=" ", end=_end) -> None:
        """Awaitable stderr helper for code already running in an event loop."""
        await Logger.stderr.async_write(*message, sep=sep, end=end)


log = Logger()
