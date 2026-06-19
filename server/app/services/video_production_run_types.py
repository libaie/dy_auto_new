"""Compatibility facade for video production run type helpers.

The implementation now lives in app.domains.video_production.video_production_run_types.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import video_production_run_types as _video_production_run_types

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _video_production_run_types
globals().update(_video_production_run_types.__dict__)
