"""Compatibility facade for image generation asset bridge services.

The implementation now lives in app.domains.image_generation.image_asset_bridge_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.image_generation import image_asset_bridge_service as _image_asset_bridge_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _image_asset_bridge_service
globals().update(_image_asset_bridge_service.__dict__)
