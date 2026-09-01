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

_Dict = dict[str, Any]
_DictOrError = _Dict | int


def _logerr(c: int, s: str) -> int:
    log.raw("validation: FAILURE")
    log.error("%s (code=%s)", s, c)
    return c


def load_grammars(path: Path) -> tuple[_Dict, _Dict] | int:
    """
    Load `fixtures/*` grammars and return the parsed data as a Python dictionary.

    This function DOES NOT validate if the files are valid.

    This function should be loaded only once per file, and the result cached.
    """
    p = grammar_parsers.get(path.suffix.casefold())

    if p is None:
        log.debug("ignoring unsupported file format %s", path)
        return error.UnsupportedGrammarFormatError

    log.info("parsing and validating (%s)", path.name)
    log.debug("selected %s parser for %s", p.__name__, path)  # ty: ignore[unresolved-attribute]

    parsed = p(path)
    if isinstance(parsed, int):
        log.error("parser rejected %s with code %s", path, parsed)
        return parsed

    container = parsed.get(uctx.cmd_router)
    if not isinstance(container, dict):
        return _logerr(error.InvalidGrammarError, "Missing 'cmd-router' object.")

    grammar = container.get(uctx.grammar)
    if not isinstance(grammar, dict):
        return _logerr(error.InvalidGrammarError, "Missing 'grammar' object.")

    info = {key: value for key, value in container.items() if key != uctx.grammar}

    errors: list[str] = []
    allowed_keys = {uctx.schema_version, uctx.grammar}
    unknown_keys = sorted(set(container) - allowed_keys)

    if unknown_keys:
        errors.append(f"Unknown key(s): {', '.join(unknown_keys)}.")

    if not grammar:
        errors.append("Grammar is empty. Cannot tokenize without valid commands.")
    elif any(not isinstance(key, str) or not isinstance(value, str) for key, value in grammar.items()):
        errors.append("Grammar is not a valid map of string commands.")

    schema_version = info.get(uctx.schema_version)
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
        return error.Abort

    log.raw(f"validation ({path.name}): OK")
    log.info("loaded %d command entr%s from %s", len(grammar), "y" if len(grammar) == 1 else "ies", path.name)
    return grammar, info
