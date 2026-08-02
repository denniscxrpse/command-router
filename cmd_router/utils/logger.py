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
from datetime import datetime
from html import escape
from typing import Any, final

from prompt_toolkit import HTML, print_formatted_text


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
        # paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)

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

    @staticmethod
    def stderr(*message: Any, sep=" ", end="\n") -> None:
        print(*message, sep=sep, end=end, file=sys.stderr, flush=True)


log = Logger()
