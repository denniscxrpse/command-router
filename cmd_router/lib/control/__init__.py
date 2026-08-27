#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Compatibility façade for control execution and fixture configuration.

Import ``Control`` and the result classes for isolated command surfaces.  For
fixture-backed applications, ``FixturesContextHolder`` and ``FixturesSetup``
define the two extension points used by a fixture module.  The module-level
control functions remain available for the default shared surface.
"""

__all__ = (
    "Control",
    "ControlInitialization",
    "ControlResult",
    "DeeperLevelContext",
    "FixturesContextHolder",
    "FixturesSetup",
    "api_symlink",
    "control",
    "deeper_level",
)

from .api import *
