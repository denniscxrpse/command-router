#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("flags", "init_flags")

import sys
from dataclasses import dataclass
from typing import Final, final

import click
from icecream import ic

_help = ["-h", "--help"]


class _CliCommand(click.Command):
    """Keep eager CLI exits from becoming tracebacks in embedded callers."""

    def main(self, *args, **kwargs):
        arguments = args[0] if args else None
        if arguments is None:
            arguments = sys.argv[1:]
        help_requested = any(argument in _help for argument in arguments)

        try:
            result = super().main(*args, **kwargs)
        except click.exceptions.Exit as e:
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
    This flag determines how the Command Router (cmd-router) should behave at startup:

    **False** (default): The `./fixtures` path contains every single grammar path. By default, we provide two files:
    `grammars.toml` and `grammars.json5`. Both of these files are loaded and parsed, and you may use them as examples.
    You can create as many TOML or JSON files as you want (JSON5 is supported), the fixtures path is the entry
    point of "grammar" files, and we read the whole directory, searching for both TOML and JSON files. Any file that
    is not supported **will be ignored**. Keep in mind that the loader is sensitive for TOML files, but we leave some
    leisure for JSON files as the "JSON with Comments" format can contain different prefixes.

    **True**: The cmd-router will start normally, but will defer from loading anything; instead, we will wait and
    listen to the HTTP port (::0). To access this port listen to the `stderr` until the port is open; we force the
    application to use a random port by default (this behavior cannot be changed). You may read the very first
    line of `stderr` to get the port number. Read the documentation so you don't have to worry about doing weird
    hacks. **Note**: You must keep listening to the `stderr` after receiving the port number, as it will tell you if
    either there was an `error` (1) or `success` (0). If `error` is caught (1), the application will not exit,
    instead, it will keep listening to the HTTP port until a valid TOML or JSON file format is provided. If `success`
    (0) is caught, anything after that number should be expected as tokenized data, and the port itself is closed/free;
    meaning that the application is ready.
    """

    ignore: frozenset[str] = frozenset({"err.json5"})
    """
    When `lazy` is **False**, this flag will force the grammar loader to ignore specific files. By default,
    we only ignore `err.json5`.

    Values may be filenames, full file paths, or directory paths. Bare filenames are faster to process; directory
    paths ignore files beneath them.
    """

    control: bool = False
    """
    This flag will tell the Command Router to initialize the `control` module. A test suite provided by the
    Command Router (cmd-router), **not recommended** to use it in production for obvious reasons.

    After determining the flags `lazy` and `ignore`, we use this flag to either (if `True`) enable or (if `False`)
    disable the initialization of the `control` module. This flag defaults to `False`.

    This module initializes the cmd-router under (either) default or custom conditions, depending on the flags; if
    `lazy` is `True`, the `control` module will not be initialized unless the user enters the correct TOML or JSON
    file to the HTTP port, otherwise (`lazy` is `False`), we'll wait until we have loaded all `./fixtures` files. The
    same goes with `ignore` as we wait to handle and load the correct specified filenames, full file paths, or
    directory paths. In summary, you'll have to wait until everything is loaded before you can use the `control` module.

    Once ready, we'll pass control to the `control` module, which will do, in summary: 1. Initialize a `shell` like
    interface (this is mainly for comfort, we **DO NOT** initialize an actual shell), you may write the commands in
    this interface, test their behaviour, and see live debug information. 2. Test of special, built-in commands which
    will help you to understand even further how the `cmd-notation` works. You can disable this by setting
    `control_no_help` to `True`.

    If you have a different grammar in `./fixtures`, or you are going to send a completely different grammar file under
    our HTTP port, we recommend to disable `control_no_help` to keep things straightforward. Following this,
    we also recommend to check `./fixtures/__init__.py` to see if your custom grammar logic's is correct, and if not,
    well, that's your problem.
    """

    control_no_help: bool = False
    """
    Disables the built-in help command in the `control` module. It has an effect only when `control` is enabled.
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
    "--control",
    is_flag=True,
    default=None,
    help="Initialize the `control` module test suite.",
)
@click.option(
    "--control-no-help",
    is_flag=True,
    default=None,
    help="Disable the built-in help command in the `control` module.",
)
def init_flags(**kwargs) -> None:
    """Initialize the process-wide environment flags from CLI options."""
    for key, value in kwargs.items():
        # `None` means that Click did not receive this option.  Leaving the
        # existing value alone is important when the command is invoked by a
        # caller that has already configured `flags` programmatically.
        if value is not None and hasattr(flags, key):
            setattr(flags, key, value)
    ic(flags)
