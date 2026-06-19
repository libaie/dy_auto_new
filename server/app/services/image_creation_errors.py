"""Compatibility facade for image generation error helpers.

The implementation now lives in app.domains.image_generation.image_creation_errors.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_creation_errors as _image_creation_errors

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_creation_errors
globals().update(_image_creation_errors.__dict__)
