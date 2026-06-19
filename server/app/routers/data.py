"""Compatibility facade for data center routes.

The implementation now lives in app.domains.content_collection.data_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.content_collection import data_router as _data_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _data_router
globals().update(_data_router.__dict__)
