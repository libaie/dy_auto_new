"""Compatibility facade for content management routes.

The implementation now lives in app.domains.content_collection.content_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.content_collection import content_router as _content_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _content_router
globals().update(_content_router.__dict__)
