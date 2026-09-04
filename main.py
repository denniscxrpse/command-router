#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from cmd_router import CommandRouter
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *
from cmd_router.utils.status import stat


def main() -> str:
    """Start the commands router and return its process exit status name."""
    log.info("starting commands router")
    try:
        CommandRouter()
    except KeyboardInterrupt:
        log.warning("interrupted; shutting down")
        return stat.Interrupted().name
    except Exception as exception:
        log.debug("an unrecoverable startup exception was raised")
        log.critical(str(exception))
        return stat.Abort().name
    log.info("commands router exited successfully")
    return stat.Success().name


if __name__ == "__main__":
    init_flags(standalone_mode=False)
    raise SystemExit(main())
