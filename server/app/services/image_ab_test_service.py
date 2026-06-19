"""Compatibility facade for image generation A/B test services.

The implementation now lives in app.domains.image_generation.image_ab_test_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_ab_test_service as _image_ab_test_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_ab_test_service
globals().update(_image_ab_test_service.__dict__)
