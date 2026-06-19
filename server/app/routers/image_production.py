"""Compatibility facade for image production routes.

The implementation now lives in
app.domains.image_generation.image_production_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_production_router as _image_production_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_production_router
globals().update(_image_production_router.__dict__)
