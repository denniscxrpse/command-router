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
    "ControlType",
    "ControlInitialization",
    "ControlResultKinds",
    "ControlResult",
    "ControlDeeperContext",
    "FixturesContextHolder",
    "FixturesSetup",
)

from .api.context import *
from .api.control import *
from .api.fittings import *
from .api.result import *
