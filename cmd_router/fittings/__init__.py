#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""
Imports the ``Fixtures`` used by the command router; ``fittings`` is a misnomer made in
haste to avoid confusion with the ``fixtures`` package.

Works as a "frontend" for the ``FixturesContextHolder`` and ``FixturesSetup`` classes;
giving direct access to the two core types.

Users may import ``Fixtures`` from here if they wish for better readability, avoid
importing from the library (``cmd_router.lib``) itself.
"""

__all__ = ("Fixtures",)

from dataclasses import dataclass
from typing import Final, final

from cmd_router.lib.control import FixturesContextHolder, FixturesSetup


@final
@dataclass(frozen=True)
class Fixtures:
    # Do not instantiate these final values; they are built at runtime
    # as parents of whatever there is in ``fixtures/__init__.py``.
    ContextHolder: Final[type[FixturesContextHolder]] = FixturesContextHolder
    Setup: Final[type[FixturesSetup]] = FixturesSetup
