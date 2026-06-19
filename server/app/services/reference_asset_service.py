"""Compatibility facade for creative library reference asset services.

The implementation now lives in app.domains.creative_library.reference_asset_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.creative_library import reference_asset_service as _reference_asset_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _reference_asset_service
globals().update(_reference_asset_service.__dict__)
