#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from cmd_router import CommandRouter, init_flags
from cmd_router.utils.context import error
from cmd_router.utils.logger import log


def main() -> int:
    """Start the command router and return its process exit status."""
    log.info("main: starting command router")
    try:
        init_flags(standalone_mode=False)
        log.debug("main: command-line flags initialized")
        CommandRouter()
    except KeyboardInterrupt:
        log.warning("main: interrupted; shutting down")
        return error.Interrupted
    except Exception as exception:
        log.debug("main: an unrecoverable startup exception was raised")
        log.critical(str(exception))
        return error.Abort
    log.info("main: command router exited successfully")
    return error.Succeed


if __name__ == "__main__":
    raise SystemExit(main())
