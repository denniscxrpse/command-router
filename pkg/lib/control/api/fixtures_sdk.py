#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Compatibility wrapper around the canonical ``src.sdk`` fixtures.

The real implementation lives in ``src.sdk.backend`` so the
public ``FixturesSDK``/``Fixtures`` façade and the control layer share one
source of truth.  This module keeps the old import paths working by
re-exporting the same objects; it adds no behavior of its own.

New code should import from ``src.sdk`` (or
``src.sdk.backend`` for advanced use):

.. code-block:: python

    from pkg.sdk import Fixtures, FixturesSDK, argument, literal

Old imports keep resolving to the identical classes:

.. code-block:: python

    from pkg.lib.control import FixturesSetup
from src.lib.control.sdk.fixtures_api import _FixtureInnerContext
"""

__all__ = (
    "FixtureInitializationError",
    "FixturesContextHolder",
    "FixturesSetup",
    "_FixtureInnerContext",
)

from pkg.sdk.backend.holder import FixturesContextHolder
from pkg.sdk.backend.settings import FixtureInitializationError
from pkg.sdk.backend.settings import _FixtureInnerContext as _FixtureInnerContext
from pkg.sdk.backend.setup import FixturesSetup
