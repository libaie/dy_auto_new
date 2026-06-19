"""Compatibility facade for AI video series episode asset scope services.

The implementation now lives in app.domains.ai_video_series.episode_asset_scope_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_video_series import episode_asset_scope_service as _episode_asset_scope_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _episode_asset_scope_service
globals().update(_episode_asset_scope_service.__dict__)
