#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

from cmd_router import CommandRouter, init_flags
from cmd_router.utils.context import error
from cmd_router.utils.logger import log


def main() -> int:
    """Start the command router and return its process exit status."""
    try:
        init_flags(standalone_mode=False)
        CommandRouter()
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        return error.Interrupted
    except Exception as exception:
        log.critical(str(exception))
        return error.Abort
    return error.Succeed


if __name__ == "__main__":
    raise SystemExit(main())
