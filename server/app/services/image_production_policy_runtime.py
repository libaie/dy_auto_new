"""Compatibility facade for image generation policy runtime helpers.

The implementation now lives in app.domains.image_generation.image_production_policy_runtime.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_production_policy_runtime as _image_production_policy_runtime

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_production_policy_runtime
globals().update(_image_production_policy_runtime.__dict__)
