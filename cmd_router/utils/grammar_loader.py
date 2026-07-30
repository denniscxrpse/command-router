__all__ = ("load_grammars",)

from pathlib import Path
from typing import Final

import json5
import tomllib

from cmd_router.lib.utils.const import *
from cmd_router.utils.cli import *
from cmd_router.utils.logger import *
from cmd_router.utils.types import LogicalDataPath, OptionalMapping

_DEFAULT_GRAMMARS: Final[Path] = paths.GRAMMARS


def _logerr(c: int, s: str = "No info") -> int:
    log.error(f"{c}: {s}")
    return c


def _parse_json(path: Path) -> OptionalMapping:
    log.info("JSON/JSONC detected, parsing and validating grammar file...", end=" ")
    try:
        with path.open("rb", encoding="utf-8") as file:
            data = json5.loads(file.read())
    except (OSError, UnicodeError, ValueError):
        return _logerr(errc.InvalidGrammarError, f"Invalid grammar (JSON): {path}")

    if not isinstance(data, dict):
        return _logerr(errc.InvalidGrammarError, f"Grammar file must contain an object: {path}")

    flags.logical_engine = "json"
    log.raw("OK")
    return data


def _parse_toml(path: Path) -> OptionalMapping:
    log.info("TOML detected, parsing and validating grammar file...", end=" ")
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError, UnicodeError):
        return _logerr(errc.InvalidGrammarError, f"Invalid grammar (TOML): {path}")

    flags.logical_engine = "toml"
    log.raw("OK")
    return data


def load_grammars(a: LogicalDataPath = None) -> OptionalMapping:
    """
    Load fixtures/grammars.toml and return the parsed TOML as a Python dictionary.

    By default, resolves the file relative to the repository root:
    <repo>/fixtures/grammars.toml

    This function should be loaded only once, and the result cached.
    """

    using_default = a is None or (isinstance(a, str) and not a.strip())
    path = _DEFAULT_GRAMMARS if using_default else Path(a)
    suffix = path.suffix.lower()

    if suffix == ".toml":
        data = _parse_toml(path)
    elif suffix in [".json", ".jsonc"]:
        data = _parse_json(path)
    else:
        _logerr(
            errc.UnsupportedGrammarFormatError,
            f"Unsupported grammar format {suffix or '<none>'!r}; " "expected .toml, .json, or .jsonc",
        )
        if using_default:
            _logerr(errc.DefaultGrammarError, f"The default grammar file is invalid: {path}")
        return errc.Abort

    if data is errc.InvalidGrammarError:
        log.critical("Cannot initialize from invalid grammar file.")
        return errc.Abort

    return data
