"""Compatibility facade for Seedance integration routes.

The implementation now lives in app.domains.seedance_integration.seedance_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.seedance_integration import seedance_router as _seedance_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _seedance_router
globals().update(_seedance_router.__dict__)
