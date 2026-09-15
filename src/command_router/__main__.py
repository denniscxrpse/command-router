#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Console entry point for the installed ``command-router`` script."""

from command_router import start


def console_main() -> int:
    """Parse ``sys.argv`` and run; returns the process exit code."""
    return start().code


if __name__ == "__main__":
    raise SystemExit(console_main())
