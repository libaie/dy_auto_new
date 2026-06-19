"""Compatibility facade for image generation selection preview services.

The implementation now lives in app.domains.image_generation.image_selection_preview_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_selection_preview_service as _image_selection_preview_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_selection_preview_service
globals().update(_image_selection_preview_service.__dict__)
