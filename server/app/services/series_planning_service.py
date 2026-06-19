"""Compatibility facade for AI video series planning services.

The implementation now lives in app.domains.ai_video_series.series_planning_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_video_series import series_planning_service as _series_planning_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _series_planning_service
globals().update(_series_planning_service.__dict__)
