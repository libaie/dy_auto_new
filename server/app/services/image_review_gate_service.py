"""Compatibility facade for image generation review gate services.

The implementation now lives in app.domains.image_generation.image_review_gate_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_review_gate_service as _image_review_gate_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_review_gate_service
globals().update(_image_review_gate_service.__dict__)
