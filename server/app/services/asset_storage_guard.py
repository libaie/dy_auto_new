"""Compatibility facade for video production asset storage guard helpers.

The implementation now lives in app.domains.video_production.asset_storage_guard.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import asset_storage_guard as _asset_storage_guard

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _asset_storage_guard
globals().update(_asset_storage_guard.__dict__)
