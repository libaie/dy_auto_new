"""Compatibility facade for video production cost helpers.

The implementation now lives in app.domains.video_production.production_cost_service.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_cost_service as _production_cost_service

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_cost_service
globals().update(_production_cost_service.__dict__)
