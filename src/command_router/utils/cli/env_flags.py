#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ["flags"]

from dataclasses import dataclass
from pathlib import Path
from typing import Final, final


@final
@dataclass
class __EnvFlags:
    ########## Functionality interactive flags ##########

    verbose_help: str | None = None
    """
    Print the field documentation (``__doc__``) for one flag, or for every flag when given ``all``. Each entry
    ends with an ``Alias(es):`` line listing the flag's CLI spellings.

    This is a read-only flag that short-circuits startup, so nothing is loaded or initialized while it is set. It
    is also silent: log output is suspended while it is set, so only the requested documentation reaches
    ``stdout``. Passing the flag bare is the same as passing ``all``. The flag is greedy and consumes the next
    argument as the flag name even when it looks like another flag, so ``-H --init`` shows the ``init``
    documentation instead of dumping every flag. Leading dashes, ``=`` signs, and surrounding quotes are
    stripped, and any click spelling works, so ``-H=init``, ``-H "init"``, ``--verbose-help --init``, ``-H -i``,
    and ``-H i`` all resolve to ``init``. Dumping every flag asks for confirmation first when run interactively,
    since it prints the whole environment.
    """

    init: Path | None = None
    """
    Scaffold a new project by copying the bundled fixture templates into a directory.

    The value names the destination. Passing the flag bare is the same as passing ``fixtures``, which creates
    ``./fixtures`` under the working directory. An existing destination must be a directory and must be empty,
    otherwise scaffolding refuses to overwrite it. Missing parent directories are created as needed.

    This flag only writes files and then exits; it does not load anything. The copied tree is validated with the
    same check the loader enforces, so the printed next step is guaranteed to work. To actually use the new
    project, run again with ``genesis`` pointing at that directory. Do not confuse the two: ``init`` creates the
    template tree, ``genesis`` selects which tree the router loads.
    """

    lazy: bool = False
    """
    Determine how the router loads grammars at startup.

    - ``False`` (default): grammars are loaded from the ``./fixtures`` directory, or from the ``genesis``
      directory when that flag is given. Two example files are provided by default, ``grammars.toml`` and
      ``grammars.json5``, which can be kept as references. The file ``err.json5`` is ignored by default through
      the ``ignore`` flag. Any number of TOML or JSON files may be added there (JSON5 is supported), while
      unsupported files are skipped. The TOML loader is strict, while the JSON loader accepts the looser
      JSON-with-comments form with different prefixes.

    - ``True``: the router defers loading and instead waits on an HTTP port for a grammar to be posted. The port
      is chosen randomly and cannot be configured; its number is printed as the very first line on ``stderr``, so
      listen there to discover it. Keep listening afterwards, because the next protocol line reports ``1`` for an
      invalid grammar and ``0`` for a valid one. On ``1`` the router stays up and keeps waiting for a valid TOML
      or JSON document. On ``0`` the grammar is accepted, the port is closed, and the router is ready.

    When combined with ``test_suite``, the suite starts only after the lazy grammar has been accepted and
    everything else is loaded.
    """

    ignore: frozenset[str] = frozenset({"err.json5"})
    """
    Force the grammar loader to ignore specific files. This applies only when ``lazy`` is ``False``. By default
    only ``err.json5`` is ignored.

    Values may be bare filenames, full file paths, or directory paths. Bare filenames are fastest to process,
    while directory paths ignore everything beneath them.

    If a file that should have been ignored is not listed here, loading stops at the first error it hits. The
    router still starts with whatever was loaded before the failure, so some commands keep working, but not all
    of them will be present.
    """

    test_suite: bool = False
    """
    Start the interactive test suite instead of booting straight into router use. This suite is meant for trying
    commands and watching live debug output, and it is not recommended for production. It defaults to ``False``,
    which leaves the suite disabled.

    The suite starts only after grammars are settled, so it respects ``lazy`` and ``ignore`` first. When ``lazy``
    is ``True``, the suite waits until a valid TOML or JSON document has been posted to the HTTP port; when
    ``False``, it waits until every file under ``./fixtures`` has been handled, skipping whatever ``ignore``
    lists. In both cases nothing in the suite runs until loading is finished.

    Once ready, control passes to the test suite loop, which does two things. It opens a shell-like prompt for
    comfort, not a real shell, where commands can be typed and their behaviour inspected with live debug
    information. It also provides the special built-in commands that further explain the command notation, which
    can be turned off with ``no_help``, or deferred to runtime with ``lazy_init_help`` in the fixture setup.
    See ``./fixtures/__init__.py``.

    The suite depends directly on how ``./fixtures/__init__.py`` is configured. Nothing is reconfigured inside
    the router startup for it, since startup has no way yet to take over control the existing ``fixtures``
    module already holds.
    """

    serve: bool = False
    """
    Read dirty command lines from ``stdin`` and print one JSON response per line on ``stderr``. There is no input
    schema: every line is fed whole to the control surface, the same path the test suite uses, so empty lines,
    plain text, and malformed commands each yield exactly one structured response instead of raising. ``stdout``
    keeps streaming live logs for a human operator, while ``stderr`` carries only protocol lines for the pipe
    consumer.

    Serve mode implies ``json_out`` and skips binding the suggestions HTTP server, so nothing else interleaves on
    ``stderr``. It takes effect only when ``test_suite`` is off. EOF ends the loop with a clean status, which
    makes this the subprocess-pipe transport: a parent process spawns the router as a child and talks to it over
    pipes.
    """

    quiet: bool = False
    """
    Disable log output on ``stdout``.

    Startup may run slightly faster without the extra writes. History is still recorded, so ``recent_messages``
    keeps working. Embedded callers that never parse CLI options can set ``CMD_ROUTER_QUIET=1`` before importing
    instead, or call ``log_handler.set_stdout_enabled(False)``.
    """

    genesis: Path | None = None
    """
    Select a custom fixtures directory as the entry point for grammar files and logic. By default the router uses
    ``./fixtures``.

    The given directory must already exist and must be a Python package, meaning it contains an ``__init__.py``
    file. It is expected to hold every grammar file and all router logic, including advanced trees. When in doubt,
    keep this directory dedicated to the router. If the directory is missing, is not a package, or fails
    validation in any way, the router will not initialize.

    This flag is optional; when it is absent the default fixtures path is used. Do not confuse it with ``init``:
    ``init`` scaffolds a fresh template tree, while ``genesis`` tells the router which existing tree to load.
    When both flags are given, ``init`` short-circuits first, so ``genesis`` has no effect on that run. When
    combined with ``lazy``, the lazy grammar is still collected over HTTP first, and ``genesis`` then selects
    the directory used for file discovery and fixture loading.
    """

    ########## Library interactive flags ##########

    no_help: bool = False
    """
    Disable compilation of the built-in ``help`` commands. This only matters when ``test_suite`` is enabled.

    When set, the ``compiler.help_action(...)`` step is skipped, which can improve startup time. The fixture
    setting ``_FixturesSetup.lazy_init_help`` achieves the same result, except compilation is deferred to runtime
    instead of skipped outright.
    """

    no_suggestions: bool = False
    """
    Disable suggestions for unknown commands. This controls how the router exposes completion information to the
    consumer:

    - If ``False`` (default): the router exposes suggestions when a command is unknown. Suggestions are the first
      ``N`` entries of ``ParseError.expected``, with ``N`` taken from the fixture setup through
      ``FixturesSetup.suggestions_set_current_size`` (internally ``_suggestions_size``).

      For example, with that size set to ``2``, consumers should expect a compact JSON response shaped like
      (only the relevant parts shown):

      .. code-block:: json

          {
            "ok": false,
            // ...
            "error": {
              "suggestions": ["word1", "word2"]
              // ...
            }
          }

      The ``error`` field is always a dictionary or ``None`` (``null``); see
      ``ControlResult._transport_value``. The top-level ``suggestions`` mirrors ``error["suggestions"]`` (``[]``
      when there is no parse error). Hints only appear when an actual error is raised, which is why they live
      under ``error``.

    - If ``True``: no suggestion list is built. Both the top-level ``suggestions`` and ``error["suggestions"]``
      are ``None``. Consumers may disable suggestions to implement their own completion handling, or to rely
      solely on the suggestions server.
    """

    max_sized_suggestions: bool = False
    """
    Force ``FixturesSetup._suggestions_size`` (``suggestions_size``) to start at
    ``_UniversalContext.SUGGESTIONS_MAX`` (``SUGGESTIONS_MAX``). This makes ``ParseError._get_suggestions``
    (``get_suggestions``) keep yielding suggestions until it runs out of candidates.

    In short, JSON responses will carry as many suggestions as possible, which is usually undesirable. Consumers
    should keep the following in mind:

    - While this flag is enabled, ``suggestions_size`` cannot be changed through ``suggestions_set_current_size``.

    - The worst case forces the library to yield up to ``SUGGESTIONS_MAX`` entries, which is ``O(n)`` with
      ``n == SUGGESTIONS_MAX``. The better case is when fewer ``expected`` candidates exist, so
      ``get_suggestions`` gives up early.

    - Keeping this flag disabled is the sensible default, since it exists mainly for testing.
    """

    suggestions_server: bool = False
    """
    Enable the suggestions server, which serves suggestions independently of the ``error["suggestions"]`` and
    top-level ``suggestions`` fields in router responses.

    Unlike inline suggestions, which wait until the library has collected the number of candidates configured by
    ``FixturesSetup.suggestions_set_current_size``, the server makes suggestions available as soon as they are
    computed. For example, given:

    .. code-block:: python

        @final
        class SetupFixtures(FixturesSetup):

            def __init__(self) -> None:
                # "gamemode": "(survival|creative) [<target>]"
                self.command_action = {
                    "gamemode": self.logic.foo,
                }

            ...

    A user can send a ``POST`` request carrying the partial ``gamemode`` command, then send a ``GET`` request
    right away to receive the available suggestions.

    The server is a lazy TCP server. Its endpoint (``localhost`` by default) and port can be configured in
    ``./fixtures/__init__.py``. When enabled, the ``lazy`` flag is ignored for its lifecycle because the server
    starts just before the router reports ready.

    ``POST`` requests need no body or specific format. ``GET`` requests always return a JSON list. Only the
    endpoint and the response shape are fixed; how requests are issued is left to the user.

    This does not disable the suggestions carried by normal router responses. Consumers can still read
    ``error["suggestions"]`` and the top-level ``suggestions`` field, even when ``no_suggestions`` or
    ``max_sized_suggestions`` is enabled.
    """

    no_suggestions_server: bool = False
    """
    Completely disable the suggestions server when set to ``True``.

    By default (``False``), the server socket is still bound even when ``suggestions_server`` is off, so disabled
    use stays visible instead of dropping the connection. Disabled requests log at error level without breaking
    the application: ``POST`` bodies are ignored with a ``204`` reply, while ``GET`` requests answer ``200`` with
    an empty JSON list.

    When this flag is ``True``, the server is not bound at all, regardless of the ``suggestions_server`` value.

    This does not change normal router behaviour while ``no_suggestions`` is ``False``.
    """

    suggestions_payload: int = 508  # (signed) INT8_MAX * 4
    """
    Cap the serialized ``suggestions`` payload at a fixed number of bytes.

    Here ``suggestions`` is a list of ``X`` strings of unbounded length, where ``X == SUGGESTIONS_MAX``. The
    serialized payload must not exceed what the consumer can handle, so this value acts as a hard limit that
    keeps responses from growing without bound.

    Payloads over the limit are truncated to fit without breaking parsing on the consumer side. Truncation emits
    warning level logs so the limit can be noticed and adjusted.
    """

    json_out: bool = False
    """
    Choose how parsed command data is emitted on ``stderr`` once the router has finished compilation and is ready
    to parse, format, and output.

    - If ``False`` (default): the data is emitted as a Python dictionary-like object. There is nothing more to
      it; it parses quickly in Python environments.

    - If ``True``: the data is emitted as a JSON-like object, which the receiving application must parse as
      needed. Enable this when the consumer expects JSON on ``stderr``.

    TOML output is currently not supported.
    """


flags: Final[__EnvFlags] = __EnvFlags()
"""Single module-level instance, access the internal CLI flags."""
