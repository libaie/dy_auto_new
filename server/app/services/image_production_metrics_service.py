"""Compatibility facade for image generation metrics services.

The implementation now lives in app.domains.image_generation.image_production_metrics_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_production_metrics_service as _image_production_metrics_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_production_metrics_service
globals().update(_image_production_metrics_service.__dict__)
