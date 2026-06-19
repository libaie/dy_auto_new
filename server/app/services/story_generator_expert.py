"""Compatibility facade for AI video series story generator expert services.

The implementation now lives in app.domains.ai_video_series.story_generator_expert.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.ai_video_series import story_generator_expert as _story_generator_expert

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _story_generator_expert
globals().update(_story_generator_expert.__dict__)
