#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("cli_flags", "describe_flags", "flag_names", "flags", "init_flags", "normalize_bare_options")

import ast
import inspect
import sys
from dataclasses import fields
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import click
from click.exceptions import Exit, NoSuchOption

from command_router.utils.logger import HELP_FLAGS, QUIET_FLAGS, VERBOSE_HELP_FLAGS

from .env_flags import __EnvFlags, flags

# Command aliases: the single source of truth for flag spellings.
# Every consumer (click options below, `_BARE_OPTION_DEFAULTS`, `cli_flags`)
# derives from these lists instead of repeating spellings. Tokens match
# exactly, so the single-char spellings stay distinct from each other and
# from `-I`. Quiet and help spellings live in `logger` so the handler can
# silence import-time output before this module (and click) is imported.
_help = list(HELP_FLAGS)
_init = ["-i", "--init"]
_quiet = list(QUIET_FLAGS)
_verbose_help = list(VERBOSE_HELP_FLAGS)

_BARE_OPTION_DEFAULTS: Final[dict[str, str]] = (
    # magic!
    lambda mappings: {alias: val for aliases, val in mappings for alias in aliases}
)([(_init, "fixtures"), (_verbose_help, "all")])
"""Explicit values injected when a valued option is passed bare.

Stock click cannot express an option that is valid both bare and valued:
a bare valued option fails parsing before any callback runs. `start`
expands these occurrences before parsing, so `--init` means
`--init fixtures` and bare `--verbose-help` means `--verbose-help all`.
"""


class _CliCommand(click.Command):
    """Keep eager CLI exits from becoming tracebacks in embedded callers."""

    # noinspection method-overriding
    def main(self, *args, **kwargs):
        arguments: Any | None = args[0] if args else None
        if arguments is None:
            arguments = sys.argv[1:]
        # noinspection not-iterable
        help_requested: bool = any(argument in _help for argument in arguments)

        try:
            # noinspection not-iterable
            result: Any = super().main(*args, **kwargs)
        except NoSuchOption as e:
            raise SystemExit(e) from None
        except Exit as e:
            # Click raises ``Exit`` for its eager help option.  With
            # ``standalone_mode=False`` that exception is normally exposed to
            # the caller, so translate it into Python's process-level exit.
            # This stops ``main.py`` before it can construct anything.
            raise SystemExit(e.exit_code) from None

        # Some Click versions consume the eager help exit when
        # ``standalone_mode=False`` is used.  Ensure the caller still stops
        # after help has been rendered instead of continuing initialization.
        if help_requested:
            raise SystemExit(0)
        return result


@lru_cache
def _normalize_verbose_name(raw: str | None) -> str | None:
    """Canonicalize a verbose-help argument to a flag name or ``"all"``.

    Leading ``=`` signs (from ``-H=init``), surrounding quotes, and leading
    dashes (so ``--init`` resolves to ``init``) are stripped. Any click
    spelling resolves, with or without its dashes, so ``-i`` and bare ``i``
    both resolve to ``init``; embedded dashes become underscores (so
    ``--test-suite`` resolves to ``test_suite``).

    Cached because the result depends only on the static click spellings;
    a miss happens only for a previously unseen name, which is rare
    (verbose help runs once at startup).
    """
    if raw is None:
        return None
    name = raw.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in ("'", '"'):
        name = name[1:-1].strip()
    name = name.lstrip("=").strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in ("'", '"'):
        name = name[1:-1].strip()
    if not name:
        return name
    for param in init_flags.params:
        if name in tuple(param.opts):
            return param.name
    if name in _help:
        return "help"
    bare = name.lstrip("-")
    for param in init_flags.params:
        if any(bare == opt.lstrip("-") for opt in tuple(param.opts)):
            return param.name
    return bare.replace("-", "_")


@lru_cache
def _split_verbose_attached(token: str) -> tuple[str, str] | None:
    """Split ``-H=value``/``--verbose-help=value`` into option plus raw value.

    Cached because the result depends only on the static verbose-help
    aliases; a miss happens only for a previously unseen CLI token.
    """
    for alias in _verbose_help:
        if token.startswith(alias + "="):
            return alias, token[len(alias) + 1 :]
    return None


@lru_cache
def _clean_attached_value(raw: str) -> str:
    """Strip quote and ``=`` padding from an attached ``-H=value`` payload.

    Cached because this is a pure string normalization; a miss happens
    only for a previously unseen payload, which is rare (startup only).
    """
    cleaned = raw.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.lstrip("=").strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()
    return cleaned


@lru_cache(maxsize=1)
def _flag_docs() -> dict[str, str]:
    """Return each ``EnvFlags`` field name mapped to its cleaned attribute docstring."""
    try:
        source = inspect.getsource(__EnvFlags)
    except OSError, TypeError:
        return {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    if not tree.body or not isinstance(tree.body[0], ast.ClassDef):
        return {}
    docs: dict[str, str] = {}
    pending: str | None = None
    for node in tree.body[0].body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            pending = node.target.id
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            pending = node.targets[0].id
        elif (
            pending is not None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            docs[pending] = inspect.cleandoc(node.value.value)
            pending = None
        else:
            pending = None
    return docs


@lru_cache(maxsize=1)
def _flag_aliases() -> dict[str, tuple[str, ...]]:
    """Return each ``EnvFlags`` field name mapped to its CLI spellings.

    Spellings come from :func:`cli_flags`, the same source the parser uses,
    so the ``Alias(es):`` trailer can never drift from what the parser
    accepts.
    """
    return {name: cli_flags(name) for name in flag_names()}


def _with_aliases(flag_name: str, docs: dict[str, str], aliases: dict[str, tuple[str, ...]]) -> str:
    """Append the ``Alias(es):`` trailer to one flag's documentation."""
    text = docs.get(flag_name, "").rstrip()
    spellings = ", ".join(aliases.get(flag_name, ()))
    if not spellings:
        return text
    return f"{text}\n\nAlias(es): {spellings}" if text else f"Alias(es): {spellings}"


def normalize_bare_options(args: list[str]) -> list[str]:
    """Expand bare `--init`/`--verbose-help` occurrences to explicit values.

    `--init` keeps the old rule: a missing value, or one that looks like
    another flag, expands to the `fixtures` default. `--verbose-help` is
    greedy instead: it consumes the next token as the flag name even when
    that token looks like another flag, so `-H --init` describes `init`
    instead of dumping every flag. Only a missing value or the `--`
    separator falls back to `all`. Attached `-H=value` forms are split so
    click never sees the `=` prefix, while values attached with `=` for
    `--init` already parse and are left alone (which is also how paths
    starting with `-` must be passed).
    """
    expanded: list[str] = []
    pending = list(args)
    verbose_aliases = set(_verbose_help)
    while pending:
        token = pending.pop(0)
        if token == "--":
            return [*expanded, token, *pending]
        attached = _split_verbose_attached(token)
        if attached is not None:
            alias, raw = attached
            expanded.extend((alias, _clean_attached_value(raw)))
            continue
        default = _BARE_OPTION_DEFAULTS.get(token)
        if default is not None:
            if token in verbose_aliases:
                if not pending or pending[0] == "--":
                    expanded.extend((token, default))
                else:
                    expanded.extend((token, pending.pop(0)))
            elif not pending or pending[0].startswith("-"):
                expanded.extend((token, default))
            else:
                expanded.append(token)
            continue
        expanded.append(token)
    return expanded


@lru_cache(maxsize=1)
def flag_names() -> tuple[str, ...]:
    """Return the declared ``EnvFlags`` field names in definition order."""
    return tuple(declared.name for declared in fields(__EnvFlags))


@lru_cache
def cli_flags(field: str) -> tuple[str, ...]:
    """Return the CLI spellings for an ``EnvFlags`` field name, or `"help"`.

    Spellings come from the click options themselves (plus `_help` for the
    built-in help, which click adds dynamically), so this can never drift
    from what the parser accepts. Use it instead of hardcoding spellings
    when scanning raw arguments before parsing.

    Cached because the click options are static after import; a miss
    happens only for a previously unseen field name, which is rare.
    Failures (unknown flags) are not cached by ``lru_cache``.

    :raises ValueError: If *field* names neither a flag nor `"help"`.
    """
    if field == "help":
        return tuple(_help)
    for param in init_flags.params:
        if param.name == field:
            return tuple(param.opts)
    raise ValueError(f"unknown flag {field!r}; expected one of: help, {', '.join(flag_names())}")


@lru_cache
def describe_flags(name: str | None) -> str:
    """Return the field documentation (``__doc__``) for one flag, or every flag when *name* is ``"all"``.

    The requested name is canonicalized first, so ``--init``, ``-i``, bare
    ``i``, ``=init``, and quoted spellings all resolve to the ``init``
    documentation. A single flag returns its bare docstring; ``"all"``
    returns every docstring as ``name:`` headed blocks. Each entry ends with
    an ``Alias(es):`` line listing the flag's CLI spellings.

    Cached like ``_flag_docs``/``_flag_aliases`` because flag documentation
    only changes when the ``__doc__`` objects change, which never happens
    at runtime; a miss happens only for a previously unseen name.
    Failures (unknown flags) are not cached by ``lru_cache``.

    :raises ValueError: If *name* is neither ``"all"`` nor a flag name.
    """
    key = _normalize_verbose_name(name) if name is not None else None
    if key != "all" and key not in flag_names():
        raise ValueError(f"unknown flag {name!r}; expected one of: all, {', '.join(flag_names())}")
    docs = _flag_docs()
    aliases = _flag_aliases()
    if key == "all":
        return "\n\n".join(
            f"{flag_name}:\n{_with_aliases(flag_name, docs, aliases)}".rstrip() for flag_name in flag_names()
        )
    assert key is not None
    return _with_aliases(key, docs, aliases)


@click.command(
    cls=_CliCommand,
    context_settings={"help_option_names": _help},
)
@click.option(
    "-L",
    "--lazy",
    is_flag=True,
    default=flags.lazy,
    help="Defer loading logical data until runtime.",
)
@click.option(
    "-I",
    "--ignore",
    multiple=True,
    default=flags.ignore,
    help="Ignore specific files or directories when loading logical data.",
)
@click.option(
    "-test",
    "--test-suite",
    is_flag=True,
    default=None,
    help="Initialize the test suite. Do not confuse with `pytest`.",
)
@click.option(
    "--serve",
    is_flag=True,
    default=flags.serve,
    help="Serve commands from stdin, one JSON response per line on stderr.",
)
@click.option(
    *_quiet,
    is_flag=True,
    default=flags.quiet,
    help="Disable all output from the logger (stdout).",
)
@click.option(
    "--genesis",
    type=Path,
    default=flags.genesis,
    help="Custom entry point for all grammar files.",
)
@click.option(
    *_verbose_help,
    type=str,
    required=False,
    default=None,
    help="Print verbose flag documentation; optionally for one flag name. Bare form describes every flag.",
)
@click.option(
    *_init,
    type=Path,
    required=False,
    default=None,
    help="Scaffold the bundled fixture templates into a directory. Bare form uses ./fixtures.",
)
@click.option(
    "--no-help",
    is_flag=True,
    default=None,
    help="Disable the built-in help commands.",
)
@click.option(
    "-S",
    "--no-suggestions",
    is_flag=True,
    flag_value=True,
    default=flags.no_suggestions,
    help="Disable suggestions for unknown commands.",
)
@click.option(
    "-M",
    "--max-sized-suggestions",
    is_flag=True,
    flag_value=True,
    default=flags.max_sized_suggestions,
    help="Enforce the suggestions list to initialize to `SUGGESTIONS_MAX`.",
)
@click.option(
    "-s",
    "--suggestions-server",
    is_flag=True,
    default=flags.suggestions_server,
    help="Enable the suggestions server.",
)
@click.option(
    "--no-suggestions-server",
    is_flag=True,
    flag_value=True,
    default=flags.no_suggestions_server,
    help="The suggestions server is completely disabled if this flag is set to ``True``.",
)
@click.option(
    "-sz",
    "--suggestions_payload",
    type=int,
    default=flags.suggestions_payload,
    help="The maximum payload for suggestions.",
)
@click.option(
    "-json",
    "--json-out",
    is_flag=True,
    default=flags.json_out,
    help="Expect JSON output instead of Python dictionary.",
)
def init_flags(**kwargs) -> None:
    """Initialize the process-wide environment flags from CLI options."""
    for key, value in kwargs.items():
        # `None` means that Click did not receive this option.  Leaving the
        # existing value alone is important when the command is invoked by a
        # caller that has already configured `flags` programmatically.
        if value is not None and hasattr(flags, key):
            if key == "ignore":
                value = frozenset(value)
            if key in ("genesis", "init") and value is not None and not isinstance(value, Path):
                value = Path(value)  # ty: ignore[invalid-argument-type]
            if key == "verbose_help" and isinstance(value, str):
                value = _normalize_verbose_name(value)
            setattr(flags, key, value)

    # Sync stdout rendering to the parsed value in both directions: parsing
    # runs after every import, which is the only point the flag is known.
    # Verbose help is silent by design, so it suspends log rendering just
    # like `quiet` does and its output stays clean without extra flags.
    # The import stays local because `logger` reads `flags` at module level,
    # so a top-level import here would be circular.
    from command_router.utils.logger import log_handler

    log_handler.set_stdout_enabled(not flags.quiet and flags.verbose_help is None)
