#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from cmd_router import CommandRouter
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *


def main() -> int:
    """Start the commands router and return its process exit status."""
    log.info("starting commands router")
    try:
        CommandRouter()
    except KeyboardInterrupt:
        log.warning("interrupted; shutting down")
        return error.Interrupted
    except Exception as exception:
        log.debug("an unrecoverable startup exception was raised")
        log.critical(str(exception))
        return error.Abort
    log.info("commands router exited successfully")
    return error.Succeed


if __name__ == "__main__":
    init_flags(standalone_mode=False)
    raise SystemExit(main())
