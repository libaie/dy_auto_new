"""Compatibility facade for image generation model selection services.

The implementation now lives in app.domains.image_generation.image_model_selection_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_model_selection_service as _image_model_selection_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_model_selection_service
globals().update(_image_model_selection_service.__dict__)
