"""Compatibility facade for video production action result helpers.

The implementation now lives in app.domains.video_production.production_action_result.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.video_production import production_action_result as _production_action_result

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _production_action_result
globals().update(_production_action_result.__dict__)
