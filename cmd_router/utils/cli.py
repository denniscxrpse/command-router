#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("flags", "init_flags")

import sys
from dataclasses import dataclass
from typing import Any, Final, final

import click
from click.exceptions import Exit, NoSuchOption

_help = ["-h", "--help"]


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

    After determining the flags ``lazy`` and ``ignore``, we use this flag to either (if ``True``) enable or 
    (if ``False``) disable the test-suite loop. This flag defaults to ``False``.

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
    `./fixtures/__init__.py` is configured. **WE DO NOT** reconfigure anything in our ``cmd_router.__init__()``
    function as we do not have a way (yet) to pass the control the existing module ``fixtures`` already has.
    """

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
    application while we simply ignore all their ``POST`` requests while their ``GET`` requests return an empty
    JSON list.
    
    If this flag is set to ``True``, the suggestions server will be completely disabled, regardless of the given 
    value of the ``suggestions_server`` flag.
    
    This does not affect the default behavior of the Command Router while ``no_suggestions`` is ``False``.
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
            setattr(flags, key, value)
