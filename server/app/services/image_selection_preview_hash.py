"""Compatibility facade for image generation selection preview hash helpers.

The implementation now lives in app.domains.image_generation.image_selection_preview_hash.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_selection_preview_hash as _image_selection_preview_hash

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_selection_preview_hash
globals().update(_image_selection_preview_hash.__dict__)
