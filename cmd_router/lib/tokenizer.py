"""Tokenize command input for the command router.

The tokenizer deliberately delegates quoting and escaping rules to `shlex`. Grammar matching belongs to a later layer;
this module only turns a command line into tokens.
"""

__all__ = ("TokenizationError", "tokenize")

import shlex

from cmd_router.utils.context import *


class TokenizationError(ValueError):
    """Raised when command input cannot be tokenized."""


def tokenize(command: str) -> list[str] | int:
    """Return shell-like tokens from *command*.

    Empty and whitespace-only input produce an empty list. Quoting and
    backslash escaping follow `shlex.split`; malformed input is exposed
    as `TokenizationError` with the original parser error as context.
    """

    if not isinstance(command, str):
        raise TypeError(f"command must be str, got {type(command).__name__}")

    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        return error.TokenizeError
