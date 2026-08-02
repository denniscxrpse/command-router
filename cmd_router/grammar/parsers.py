#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("grammar_parsers",)

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import json5
import tomllib

from cmd_router.utils.context import *
from cmd_router.utils.logger import *

_Dict = dict[str, Any]
_DictOrError = _Dict | int
_Tstr = tuple[str, ...]

_TOML_EXTENSIONS: Final[_Tstr] = (".toml",)
_JSON_EXTENSIONS: Final[_Tstr] = (".json", ".jsonc", ".json5")


def parse_json(f: Path) -> _DictOrError:
    try:
        with f.open("r", encoding="utf-8") as file:
            data = json5.loads(file.read())
        if not isinstance(data, dict):
            log.raw("Grammar file must contain an object.")
            return error.InvalidGrammarError
    except (OSError, UnicodeError, ValueError):
        log.raw("Invalid.")
        return error.InvalidGrammarError
    return data


def parse_toml(f: Path) -> _DictOrError:
    try:
        with f.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        log.raw("Invalid.")
        return error.InvalidGrammarError
    return data


grammar_parsers: Final[dict[str, Callable[[Path], _DictOrError]]] = {
    **dict.fromkeys(_TOML_EXTENSIONS, parse_toml),
    **dict.fromkeys(_JSON_EXTENSIONS, parse_json),
}
