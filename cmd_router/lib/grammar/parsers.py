#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("grammar_parsers",)

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import json5

from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import Status, stat

_Dict = dict[str, Any]
_DictOrError = _Dict | Status
_Tstr = tuple[str, ...]

_TOML_EXTENSIONS: Final[_Tstr] = (".toml",)
_JSON_EXTENSIONS: Final[_Tstr] = (".json", ".jsonc", ".json5")


def parse_json(f: Path) -> _DictOrError:
    log.debug("reading JSON5 file %s", f)
    try:
        with f.open("r", encoding="utf-8") as file:
            data = json5.loads(file.read())
        if not isinstance(data, dict):
            log.raw(f"{f.name}: FAILURE")
            log.error("%s must contain an object", f)
            return stat.InvalidGrammarError()
    except (OSError, UnicodeError, ValueError) as exception:
        log.raw(f"{f.name}: FAILURE")
        log.error("could not read JSON5 file %s: %s", f, exception)
        return stat.InvalidGrammarError()
    log.debug("read JSON5 object from %s", f)
    return data


def parse_toml(f: Path) -> _DictOrError:
    log.debug("reading TOML file %s", f)
    try:
        with f.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError, UnicodeError) as exception:
        log.raw(f"{f.name}: FAILURE")
        log.error("could not read TOML file %s: %s", f, exception)
        return stat.InvalidGrammarError()
    log.debug("read TOML object from %s", f)
    return data


grammar_parsers: Final[dict[str, Callable[[Path], _DictOrError]]] = {
    **dict.fromkeys(_TOML_EXTENSIONS, parse_toml),
    **dict.fromkeys(_JSON_EXTENSIONS, parse_json),
}
