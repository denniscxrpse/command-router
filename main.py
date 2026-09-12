#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

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
