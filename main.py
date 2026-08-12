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
    except KeyboardInterrupt as exception:
        code = error.exit_code(exception)
        log.warning(f"Interrupted ({code}).")
        return code
    except Exception as exception:
        code = error.exit_code(exception)
        log.critical(f"Fatal error ({code}): {exception!r}")
        return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
