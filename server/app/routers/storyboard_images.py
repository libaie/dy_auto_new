"""Compatibility facade for storyboard image routes.

The implementation now lives in app.domains.storyboard_images.storyboard_images_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.storyboard_images import storyboard_images_router as _storyboard_images_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _storyboard_images_router
globals().update(_storyboard_images_router.__dict__)
