"""Compatibility facade for agency operations routes.

The implementation now lives in app.domains.agency_operations.agency_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.agency_operations import agency_router as _agency_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _agency_router
globals().update(_agency_router.__dict__)
