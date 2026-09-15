#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ["main", "init_flags"]

import os
import sys

if any(v in sys.argv[1:] for v in ["--quiet", "-q"]):
    # Flag parsing runs after every import, but importing the router already
    # logs; seed quiet mode through the environment so the handler is born
    # silent. `init_flags` confirms it once options are parsed.
    os.environ["CMD_ROUTER_QUIET"] = "1"

from pkg import CommandRouter
from pkg.utils.cli import *
from pkg.utils.logger import *
from pkg.utils.status import *


def main(entry: tuple[str, ...] | None = None) -> Status:
    """Start the command router and return its process exit status name.

    When *entry* is given, it is parsed as CLI arguments first, so importers
    can initialize the flag environment without touching ``sys.argv``::

        main(("--serve", "--quiet"))

    An absent *entry* leaves already-configured flags alone; an empty tuple
    parses as bare argv and resets every flag to its default. Invalid
    entries raise ``SystemExit`` exactly like the command line does.
    """
    if entry is not None:
        init_flags(list(entry), standalone_mode=False)
    log.info("starting command router")
    ultima: Status
    try:
        ultima = CommandRouter().main
    except KeyboardInterrupt:
        log.warning("interrupted; shutting down")
        return stat.Interrupted()
    except Exception as exception:
        log.debug("unrecoverable startup exception was raised")
        log.critical(str(exception))
        return stat.Abort()
    log.info("command router exited with code %s (%s)", ultima.code, ultima.name)
    log.info("contract message (if any): %s", ultima.message)
    return ultima


if __name__ == "__main__":
    init_flags(standalone_mode=False)
    raise SystemExit(main().code)
