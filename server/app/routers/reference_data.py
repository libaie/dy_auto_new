"""Compatibility facade for reference-data routes.

The implementation now lives in
app.domains.creative_library.reference_data_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.creative_library import reference_data_router as _reference_data_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _reference_data_router
globals().update(_reference_data_router.__dict__)
