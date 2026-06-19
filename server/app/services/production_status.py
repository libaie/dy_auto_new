"""Compatibility facade for video production status constants.

The implementation now lives in app.domains.video_production.production_status.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_status as _production_status

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_status
globals().update(_production_status.__dict__)
