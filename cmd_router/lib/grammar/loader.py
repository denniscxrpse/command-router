#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("load_grammars",)

from pathlib import Path
from typing import Any

from cmd_router.lib.grammar.parsers import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import Status, stat

_Dict = dict[str, Any]
_DictOrError = _Dict | Status


def _logerr(c: Status, s: str) -> Status:
    log.raw("validation: FAILURE")
    log.error("%s (code=%s)", s, c)
    return c


def load_grammars(path: Path) -> tuple[_Dict, _Dict] | Status:
    """
    Load `fixtures/*` grammars and return the parsed data as a Python dictionary.

    This function DOES NOT validate if the files are valid.

    This function should be loaded only once per file, and the result cached.
    """
    p = grammar_parsers.get(path.suffix.casefold())

    if p is None:
        log.debug("ignoring unsupported file format %s", path)
        return stat.UnsupportedGrammarFormatError()

    log.info("parsing and validating (%s)", path.name)
    log.debug("selected %s parser for %s", p.__name__, path)  # ty: ignore[unresolved-attribute]

    parsed = p(path)
    if isinstance(parsed, Status):
        log.error("parser rejected %s with code %s", path, parsed)
        return parsed

    container = parsed.get(uctx.CMD_ROUTER_SERIAL)
    if not isinstance(container, dict):
        return _logerr(stat.InvalidGrammarError(), "Missing 'cmd-router' object.")

    grammar = container.get(uctx.GRAMMAR_SERIAL)
    if not isinstance(grammar, dict):
        return _logerr(stat.InvalidGrammarError(), "Missing 'grammar' object.")

    info = {key: value for key, value in container.items() if key != uctx.GRAMMAR_SERIAL}

    errors: list[str] = []
    allowed_keys = {uctx.SCHEMA_VERSION_SERIAL, uctx.GRAMMAR_SERIAL}
    unknown_keys = sorted(set(container) - allowed_keys)

    if unknown_keys:
        errors.append(f"Unknown key(s): {', '.join(unknown_keys)}.")

    if not grammar:
        errors.append("Grammar is empty. Cannot tokenize without valid commands.")
    elif any(not isinstance(key, str) or not isinstance(value, str) for key, value in grammar.items()):
        errors.append("Grammar is not a valid map of string commands.")

    schema_version = info.get(uctx.SCHEMA_VERSION_SERIAL)
    if not info or schema_version is None:
        errors.append("Info is invalid. Cannot tokenize without understanding the context.")
    elif type(schema_version) is not int or schema_version not in uctx.VALID_SCHEMAS:
        errors.append(f"Unsupported schema version: {schema_version}.")

    if errors:
        log.raw(f"validation ({path.name}): FAILURE")
        log.warning("Validation failed!")
        log.debug(f"Parsed data: {parsed}, from: {path}")
        for e in errors:
            log.error("%s", e)
        return stat.Abort()

    log.raw(f"validation ({path.name}): OK")
    log.info("loaded %d command entr%s from %s", len(grammar), "y" if len(grammar) == 1 else "ies", path.name)
    return grammar, info
