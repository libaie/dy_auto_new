"""Compatibility facade for video library routes.

The implementation now lives in app.domains.video_library.videos_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_library import videos_router as _videos_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _videos_router
globals().update(_videos_router.__dict__)
