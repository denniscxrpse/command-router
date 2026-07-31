__all__ = ("load_grammars",)

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import json5
import tomllib

from cmd_router.utils.context import *
from cmd_router.utils.logger import *

_Dict = dict[str, Any]
_DictOrError = _Dict | int
_TOML_EXTENSIONS: Final[tuple[str, ...]] = (".toml",)
_JSON_EXTENSIONS: Final[tuple[str, ...]] = (".json", ".jsonc", ".json5")


def _logerr(c: int, s: str) -> int:
    log.raw(f"{c} - {s}")
    return c


def _parse_json(path: Path) -> _DictOrError:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json5.loads(file.read())
        if not isinstance(data, dict):
            return _logerr(error.InvalidGrammarError, "Grammar file must contain an object.")
    except (OSError, UnicodeError, ValueError):
        return _logerr(error.InvalidGrammarError, "Invalid.")
    return data


def _parse_toml(path: Path) -> _DictOrError:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        return _logerr(error.InvalidGrammarError, "Invalid.")
    return data


def load_grammars(path: Path) -> tuple[_Dict, _Dict] | int:
    """
    Load `fixtures/*` grammars and return the parsed data as a Python dictionary.

    This function DOES NOT validate if the files are valid.

    This function should be loaded only once per file, and the result cached.
    """
    parsers: dict[str, Callable[[Path], _DictOrError]] = {
        **dict.fromkeys(_TOML_EXTENSIONS, _parse_toml),
        **dict.fromkeys(_JSON_EXTENSIONS, _parse_json),
    }
    p = parsers.get(path.suffix.casefold())

    if p is None:
        return error.UnsupportedGrammarFormatError

    log.info(f"Parsing and validating ({path.name}):", end=" ")

    parsed = p(path)
    if isinstance(parsed, int):
        return parsed

    container = parsed.get("cmd-router")
    if not isinstance(container, dict):
        return _logerr(error.InvalidGrammarError, "Missing 'cmd-router' object.")

    grammar = container.get("grammar")
    if not isinstance(grammar, dict):
        return _logerr(error.InvalidGrammarError, "Missing 'grammar' object.")

    info = {key: value for key, value in container.items() if key != "grammar"}

    errors: list[str] = []
    allowed_keys = {"schema-version", "grammar"}
    unknown_keys = sorted(set(container) - allowed_keys)

    if unknown_keys:
        errors.append(f"Unknown key(s): {', '.join(unknown_keys)}.")

    if not grammar:
        errors.append("Grammar is empty. Cannot tokenize without valid commands.")
    elif any(not isinstance(key, str) or not isinstance(value, str) for key, value in grammar.items()):
        errors.append("Grammar is not a valid map of string commands.")

    schema_version = info.get("schema-version")
    if not info or schema_version is None:
        errors.append("Info is invalid. Cannot tokenize without understanding the context.")
    elif type(schema_version) is not int or schema_version not in valid_schemas:
        errors.append(f"Unsupported schema version: {schema_version}.")

    if errors:
        log.raw("FAILED")
        log.warning("Validation failed!")
        log.debug(f"Parsed data: {parsed}, from: {path}")
        for e in errors:
            log.error(e)
        return error.Abort

    log.raw("OK")
    return grammar, info
