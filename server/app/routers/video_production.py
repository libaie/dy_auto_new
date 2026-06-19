"""Compatibility facade for video production routes.

The implementation now lives in app.domains.video_production.video_production_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import video_production_router as _video_production_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _video_production_router
globals().update(_video_production_router.__dict__)
