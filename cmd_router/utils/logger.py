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
from typing import Any, Final, TextIO, final

from prompt_toolkit import HTML, print_formatted_text


class _CompletedWrite:
    """An awaitable that is already complete.

    ``log.stderr`` remains usable by synchronous code, while callers that are
    already asynchronous may also write ``await log.stderr(...)``. The write
    happens before this object is returned, so old call sites do not leave an
    un-awaited coroutine behind.
    """

    def __await__(self):
        if False:
            yield None
        return None


class _LockedStderr:
    """Serialize writes to a stream shared by embedded command runners."""

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
    """Callable stderr writer supporting both synchronous and async callers."""

    def __init__(self, lock: RLock) -> None:
        self._lock = lock

    def __call__(self, *message: Any, sep: str = " ", end: str = "\n") -> Awaitable[None]:
        text = sep.join(str(arg) for arg in message) + end
        with self._lock:
            print(text, sep="", end="", file=sys.stderr, flush=True)
        return _CompletedWrite()

    async def async_write(self, *message: Any, sep: str = " ", end: str = "\n") -> None:
        self(*message, sep=sep, end=end)


@final
class LoggerHandler:
    def __init__(self) -> None:
        """
        The LoggerHandler prints colorful logs to terminal and Stores logs in disk and writes them to a file.
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
        """Logs a message into a file and prompts the same message into the stream with colored formatting."""
        m: str = sep.join(str(arg) for arg in message)
        final_message = self.get_final_message(level, m + end)

        # Print to stdout
        print_formatted_text(self.html(final_message["msg"], level), sep="", end="")

    @staticmethod
    def raw(*message: Any, sep: str, end: str) -> None:
        """
        Logs a message into a file and prompts the same message into the stream.

        Against the log method, this method will simply not add the datetime and level into the stream;
        this also means that levels are not considered a rule, always printing into the stdout.

        Separators and final characters will still apply to the formatting, including injected HTML messages.
        """
        m: str = sep.join(str(arg) for arg in message)
        final_message = m + end

        print_formatted_text(HTML(final_message), sep="", end="")


log_handler = LoggerHandler()


class Logger:
    @staticmethod
    def debug(*message: Any, sep=" ", end="\n") -> None:
        log_handler.log(_log.DEBUG, *message, sep=sep, end=end)

    @staticmethod
    def info(*message: Any, sep=" ", end="\n") -> None:
        log_handler.log(_log.INFO, *message, sep=sep, end=end)

    @staticmethod
    def warning(*message: Any, sep=" ", end="\n") -> None:
        log_handler.log(_log.WARNING, *message, sep=sep, end=end)

    @staticmethod
    def error(*message: Any, sep=" ", end="\n") -> None:
        log_handler.log(_log.ERROR, *message, sep=sep, end=end)

    @staticmethod
    def critical(*message: Any, sep=" ", end="\n") -> None:
        log_handler.log(_log.CRITICAL, *message, sep=sep, end=end)

    @staticmethod
    def raw(*message: Any, sep=" ", end="\n") -> None:
        log_handler.raw(*message, sep=sep, end=end)

    stderr: Final[_StderrWriter] = _StderrWriter(log_handler._stderr_lock)

    @staticmethod
    async def stderr_async(*message: Any, sep=" ", end="\n") -> None:
        """Awaitable stderr helper for code already running in an event loop."""
        await Logger.stderr.async_write(*message, sep=sep, end=end)


log = Logger()
