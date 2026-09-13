#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

import os
import sys

argv = sys.argv[1:]
if "--quiet" in argv or "-q" in argv:
    # Flag parsing runs after every import, but importing the router already
    # logs; seed quiet mode through the environment so the handler is born
    # silent. `init_flags` confirms it once options are parsed.
    os.environ["CMD_ROUTER_QUIET"] = "1"

from cmd_router import CommandRouter
from cmd_router.utils.cli import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import *


def main() -> Status:
    """Start the command router and return its process exit status name."""
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
