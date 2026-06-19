"""Compatibility facade for image creation routes.

The implementation now lives in
app.domains.image_generation.image_creation_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_creation_router as _image_creation_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_creation_router
globals().update(_image_creation_router.__dict__)
