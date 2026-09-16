#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("cli_flags", "describe_flags", "flag_names", "flags", "init_flags", "normalize_bare_options")

import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Final, final

import click
from click.exceptions import Exit, NoSuchOption

from .logger import HELP_FLAGS, QUIET_FLAGS

# Command aliases: the single source of truth for flag spellings.
# Every consumer (click options below, `_BARE_OPTION_DEFAULTS`, `cli_flags`)
# derives from these lists instead of repeating spellings. Tokens match
# exactly, so the single-char spellings stay distinct from each other and
# from `-I`. Quiet and help spellings live in `logger` so the handler can
# silence import-time output before this module (and click) is imported.
_help = list(HELP_FLAGS)
_init = ["-i", "--init"]
_quiet = list(QUIET_FLAGS)
_verbose_help = ["-H", "--verbose-help"]


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


@final
@dataclass
class EnvFlags:
    ########## Functionality interactive flags ##########

    verbose_help: str | None = None
    """
    Pretty prints a help message with verbose information following the ``__doc__`` variable from ``EnvFlags`` (flags).
    
    If ``None`` (no specific flag was given) this will print every single variable from flags after a confirmation 
    menu. This menu briefly tells the user that they can specify a variable instead of printing the entire flags object.
    """

    init: Path | None = None
    """
    Specifies the entry point to initialize a new project.
    
    We follow the example fixture from ``_example/``, where we copy the entire directory unto the user's directory. 
    The user can specify a different folder name (if Path is not dir or this flag is ``None``), or directory location
    (if it exists) where the user can store their grammars and fixtures files.
    
    The user must use the ``genesis`` flag to initialize their project accordingly. 
    """

    lazy: bool = False
    """
    This flag determines how the Command Router (``cmd-router``) should behave at startup:

    - ``False`` (**default**): The ``./fixtures`` path contains every single grammar path. By default, we provide two 
      files: ``grammars.toml`` and ``grammars.json5``. Both of these files are loaded and parsed, and you may use them 
      as examples. The file ``err.json5`` is ignored by default; unless the flag ``ignore`` is modified, it won't be 
      loaded.
      You can create as many TOML or JSON files as you want (JSON5 is supported), the ``fixtures`` path is the entry
      point of "grammar" files, and we read the whole directory, looking for both TOML and JSON files. Any file that
      is not supported **will be ignored**. Keep in mind that the loader is sensitive for TOML files, but we leave some
      leisure for JSON files as the "JSON with Comments" format can contain different prefixes.

    - ``True``: The ``cmd-router`` will start normally, but will defer from loading anything; instead, we will wait and
      listen to the HTTP port (``::0``). To access this port listen to the ``stderr`` until the port is open; we force 
      the application to use a random port by default (this behavior cannot be changed). You may read the very first
      line of `stderr` to get the port number. Read the documentation so you don't have to worry about doing weird
      hacks. 
      **Note**: You must keep listening to the `stderr` after receiving the port number, as it will tell you if either 
      there was an ``error`` (``1``) or `success` (``0``). If ``error`` is caught (``1``), the application 
      **will not exit**, instead, it will keep listening to the HTTP port until a valid TOML or JSON file format 
      is provided. If ``success`` (``0``) is caught, anything after that number should be expected as tokenized data, 
      and the port itself is closed/free; meaning that the application is ready.
    """

    ignore: frozenset[str] = frozenset({"err.json5"})
    """
    When ``lazy`` is ``False``, this flag will force the grammar loader to ignore specific files. By default,
    we only ignore ``err.json5``.

    Values may be filenames, full file paths, or directory paths. Bare filenames are faster to process; directory
    paths ignore files beneath them.
    
    If you do not set your ``ignore`` flag correctly, the library will stop at the very first error it encounters.
    The library will still work, and you can still use your commands as intended, but not all of them will be loaded.
    """

    test_suite: bool = False
    """
    This flag will tell the Command Router to initialize the ``_test_suite_loop``. A **test suite** provided by the
    Command Router (cmd-router), **not recommended** to use it in production for obvious reasons. This is how the
    cmd-router behaves when it is invoked with this flag enabled (``True``).

    (if ``False``) disable the test-suite loop. This flag defaults to ``False``.
    After determining the flags ``lazy`` and ``ignore``, we use this flag to either (if ``True``) enable or 

    This module initializes the cmd-router under (either) default or custom conditions, depending on the flags; if
    ``lazy`` is ``True``, the **test suite** will not be initialized until the user enters the correct TOML or JSON
    file to the HTTP port, otherwise (``lazy`` is ``False``), we'll wait until we have loaded all ``./fixtures/*``
    files. The same goes with ``ignore`` as we wait to handle and load the correct specified filenames, full file paths,
    or directory paths. In summary, you'll have to wait until everything is loaded before you can use the **test
    suite**.

    Once ready, we'll pass control to the ``_test_suite_loop``, which will do, in summary:

    1. Initialize a shell like interface (this is mainly for comfort, we **DO NOT** initialize an actual shell); you
       may write the commands in this interface, test their behaviour, and see live debug information.

    2. Test of special, built-in commands which will help you to understand even further how the `cmd-notation` works.
       You can disable this by setting ``no_help`` to ``True``, or use ``lazy_init_help`` at ``_FixturesSetup``.
       See: `./fixtures/__init__.py`.
    
    Note: The "test suite," meant to test behaviour and see live debug information, is directly dependant on how
    `./fixtures/__init__.py` is configured. **WE DO NOT** reconfigure anything in our ``src.__init__()``
    function as we do not have a way (yet) to pass the control the existing module ``fixtures`` already has.
    """

    serve: bool = False
    """
    Read dirty command lines from ``stdin``; the control layer prints one JSON response per line on ``stderr``. There 
    is no input schema: every line is fed whole to the control surface (the same path the test suite uses), 
    so empty lines, plain text, and malformed commands all yield exactly one structured response instead of raising. 
    ``stdout`` keeps streaming live logs for a human operator, while ``stderr`` carries only protocol lines for the 
    pipe consumer.

    Serve mode implies ``json_out`` and skips binding the suggestions HTTP server, so nothing else can interleave on 
    ``stderr``. Takes effect only when ``test_suite`` is off. EOF ends the loop with a clean status, which makes this
    the subprocess-pipe transport: a parent process spawns the router as a child and talks to it over pipes.
    """

    quiet: bool = False
    """
    Disables printing of logs to ``stdout``.

    If you enable this flag, it will skip the printing of logs to ``stdout``, which may improve performance.
    History is still recorded, so ``recent_messages`` keeps working. Embedded
    callers that never parse CLI options may set ``CMD_ROUTER_QUIET=1`` before
    importing instead, or call ``log_handler.set_stdout_enabled(False)``.
    """

    genesis: Path | None = None
    """
    By default, the command router uses the ``./fixtures`` (fixtures) path as the entry point for all grammar files, 
    and logic in general.

    This flag allows the user to change the fixtures path if needed.

    The given directory must be a module path, and it must contain a ``__init__.py`` (init) file. This directory is 
    expected to contain all the grammar files and logic for the command router, including those advanced ones. In 
    uncertainty: if the given directory is not a module path, or does not contain a init file, we will not initialize 
    the command router. Our recommendation is to keep this directory path exclusive to the command router to handle.

    This flag is optional, and if not provided, the command router will use the default fixtures path; this is only 
    true when the flag is not given, if the flag provided is incorrect or fails in any way, we will not initialize the 
    command router.
    
    Do not confuse with ``init`` flag.
    """

    ########## Library interactive flags ##########

    no_help: bool = False
    """
    Disables compilation of the built-in ``help`` commands. This has an effect only when ``test_suite`` is enabled.
    
    If you enable this flag, it will skip the compilation of step of ``compiler.help_action(...)``, which may improve
    startup performance.
    
    Using internal variable ``_FixturesSetup.lazy_init_help`` does the exact same thing as this flag,
    but instead of compiling everything at startup, we compile at runtime.
    """

    no_suggestions: bool = False
    """
    Disables suggestions for unknown commands. This has a global effect on how the Command Router (``cmd-router``)
    exposes information to the consumer:

    - If ``False`` (**default**): The ``cmd-router`` exposes suggestions when the command is unknown.
      Suggestions are the first ``N`` of ``ParseError.expected``, with ``N`` from the fixture child via
      ``FixturesSetup.suggestions_set_current_size`` (internally ``_suggestions_size``).

      For example: with ``suggestions_set_current_size`` set to ``2``, consumers should expect a compact
      JSON response shaped like (stripped to the important parts):
      
      .. code-block:: json

          {
            "ok": false,
            // ...
            "error": {
              "suggestions": ["word1", "word2"]
              // ...
            }
          }

      The ``error`` field factory is always a dictionary or ``None`` (``null``); see
      ``ControlResult._transport_value``. The top-level ``suggestions`` mirrors
      ``error["suggestions"]`` (``[]`` when no parse error exists). Hints appear only when an
      actual error is raised, which is why they live under ``error``.

    - If ``True``: No suggestion list is built. Both the top-level ``suggestions`` and
      ``error["suggestions"]`` are ``None``. Consumers might disable this to handle their own
      suggestions in their application, or to only rely on the suggestions server.
    """

    max_sized_suggestions: bool = False
    """
    Enforces the reference of ``FixturesSetup._suggestions_size`` (``suggestions_size``) to initialize with
    ``_UniversalContext.SUGGESTIONS_MAX`` (``SUGGESTIONS_MAX``) by default. Using this flag will enforce the
    ``ParseError._get_suggestions`` (``get_suggestions``) to spit out suggestions until it burns out.

    In summary: it will allow JSON responses to include as many suggestions as possible (very bad). Consumers should
    keep in mind the following points:

    - This flag will not allow consumers to change the value of ``suggestions_size`` if used.

    - The absolute worst scenario of this flag being enabled, is enforcing the library to yield until a number of
      ``SUGGESTIONS_MAX`` entries are given (``O(n)`` with ``n == SUGGESTIONS_MAX``); the best scenario is
      ``get_suggestions`` giving up early when fewer ``expected`` candidates exist to save you.

    - The real best scenario is keeping this flag disabled because it is meant for testing.
    """

    suggestions_server: bool = False
    """
    Enables the suggestions server, allowing consumers to retrieve suggestions independently
    of the command router's ``error["suggestions"]`` and top-level ``suggestions`` fields.
    
    The suggestions server provides suggestions as soon as they are available, rather than
    waiting for the library to collect the number of candidates configured by
    ``FixturesSetup.suggestions_set_current_size``. For example, given:
    
    .. code-block:: python
    
        @final
        class SetupFixtures(FixturesSetup):
    
            def __init__(self) -> None:
                # "gamemode": "(survival|creative) [<target>]"
                self.command_action = {
                    "gamemode": self.logic.foo,
                }
    
            ...
    
    A user can send a ``POST`` request for the ``gamemode`` command, then immediately send
    a ``GET`` request to receive the available suggestions.
    
    The server is a lazy TCP server. Its endpoint (``localhost`` by default) and port can be
    configured in ``./fixtures/__init__.py``. When enabled, the ``lazy`` flag is ignored
    because the server initializes just before the command router is ready.
    
    ``POST`` requests require no body or specific format. ``GET`` requests must return a JSON
    list. The implementation of requests is left to the user; only the endpoint and response
    format are provided.
    
    This does not disable suggestions exposed by the command router. Consumers can still
    retrieve them from ``error["suggestions"]`` or the top-level ``suggestions`` field,
    including when ``no_suggestions`` or ``max_sized_suggestions`` is enabled.
    """

    no_suggestions_server: bool = False
    """
    The suggestions server is completely disabled if this flag is set to ``True``.
    
    By default (``False``), we do not disable the suggestions server as a way to flood the ``stdout`` with error level 
    logs. This is a way to tell the user that the suggestions server is disabled without completely breaking their
    application, meanwhile we simply ignore all their ``POST`` requests while their ``GET`` requests return an empty
    JSON list.
    
    If this flag is set to ``True``, the suggestions server will be completely disabled, regardless of the given 
    value of the ``suggestions_server`` flag.
    
    This does not affect the default behavior of the Command Router while ``no_suggestions`` is ``False``.
    """

    suggestions_payload: int = 508  # (signed) INT8_MAX * 4
    """
    The maximum number of bytes that the suggestions list will respond from the Command Router.
    
    Here, ``suggestions`` is a list of exactly ``X`` strings of unbounded length, where ``X == SUGGESTIONS_MAX``. 
    The serialized ``suggestions`` payload MUST NOT exceed the consumer’s maximum supported payload size in bytes.
    
    The given value will serve as a hard limit for the size of the suggestions payload, ensuring that the consumer 
    does not receive an excessively large payload.
    
    Payloads who exceed this limit will be truncated to fit within the maximum supported payload size without breaking 
    the consumer’s ability to parse the data. Warning level logs will be emitted to notify the user of the truncation.
    """

    json_out: bool = False
    """
    Every single time the Command Router (``cmd-router``) finishes compilation, and is ready to start parsing, 
    formatting, and outputting commands (data) into the ``stderr``, we either do two things depending on this flag:

    - If ``False`` (**default**): The exposed data in the ``stderr`` is exposed as a Python dictionary like object.
      There is nothing more to it, it's simply a dictionary that can be quickly parsed in Python environments.

    - If ``True``: The exposed data will be a JSON like object, requiring parsing in your application depending on 
      your requirements. You must set this flag to ``True`` if your application expects the ``stderr`` parsed data to 
      be JSON.

    Currently, TOML is not supported when exposing parsed data.
    """


flags: Final[EnvFlags] = EnvFlags()
"""Single module-level instance, access the internal CLI flags."""


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


def normalize_bare_options(args: list[str]) -> list[str]:
    """Expand bare `--init`/`--verbose-help` occurrences to explicit values.

    Only exact tokens are expanded, and only when no value follows (the next
    token is missing, another flag, or the `--` separator, which also stops
    further expansion). Values attached with `=` (``--init=dir``) already
    parse and are left alone, which is also how paths starting with `-`
    must be passed.
    """
    expanded: list[str] = []
    pending = list(args)
    while pending:
        token = pending.pop(0)
        if token == "--":
            return [*expanded, token, *pending]
        default = _BARE_OPTION_DEFAULTS.get(token)
        if default is not None and (not pending or pending[0].startswith("-")):
            expanded.extend((token, default))
        else:
            expanded.append(token)
    return expanded


def flag_names() -> tuple[str, ...]:
    """Return the declared ``EnvFlags`` field names in definition order."""
    return tuple(declared.name for declared in fields(EnvFlags))


def cli_flags(field: str) -> tuple[str, ...]:
    """Return the CLI spellings for an ``EnvFlags`` field name, or `"help"`.

    Spellings come from the click options themselves (plus `_help` for the
    built-in help, which click adds dynamically), so this can never drift
    from what the parser accepts. Use it instead of hardcoding spellings
    when scanning raw arguments before parsing.

    :raises ValueError: If *field* names neither a flag nor `"help"`.
    """
    if field == "help":
        return tuple(_help)
    for param in init_flags.params:
        if param.name == field:
            return tuple(param.opts)
    raise ValueError(f"unknown flag {field!r}; expected one of: help, {', '.join(flag_names())}")


def describe_flags(name: str | None) -> str:
    """Describe one flag, or every flag when *name* is ``"all"``.

    Each entry shows the declared type, the default, and the current value.
    Field docstrings are source-only text and cannot be read back at
    runtime, so this reports live state instead of prose.

    :raises ValueError: If *name* is neither ``"all"`` nor a flag name.
    """
    if name != "all" and name not in flag_names():
        raise ValueError(f"unknown flag {name!r}; expected one of: all, {', '.join(flag_names())}")
    declared = {field.name: field for field in fields(EnvFlags)}
    selected = flag_names() if name == "all" else (name,)
    lines: list[str] = []
    for flag_name in selected:
        field = declared[flag_name]
        annotation = field.type if isinstance(field.type, str) else str(field.type)
        if annotation.startswith("<class '") and annotation.endswith("'>"):
            annotation = annotation[len("<class '") : -len("'>")]
        lines.append(f"{flag_name}: {annotation} (default {field.default!r}, current {getattr(flags, flag_name)!r})")
    return "\n".join(lines)


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
            setattr(flags, key, value)

    # Sync stdout rendering to the parsed value in both directions: parsing
    # runs after every import, which is the only point the flag is known.
    # The import stays local because `logger` reads `flags` at module level,
    # so a top-level import here would be circular.
    from command_router.utils.logger import log_handler

    log_handler.set_stdout_enabled(not flags.quiet)
