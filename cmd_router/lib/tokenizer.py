#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Tokenize command input for the command router.

The tokenizer deliberately delegates quoting and escaping rules to `shlex`. Grammar matching belongs to a later layer;
this module only turns a command line into tokens.
"""

__all__ = ("tokenize",)

import shlex

from cmd_router.utils.context import error


def tokenize(command: str) -> list[str] | int:
    """Return shell-like tokens from *command*.

    Empty and whitespace-only input produce an empty list. Quoting and
    backslash escaping follow `shlex.split`. Unsupported input types and
    malformed command strings return the corresponding tokenizer error code.
    """

    if not isinstance(command, str):
        return error.TokenizeUnsupportedTypeError

    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        return error.TokenizeInvalidError
