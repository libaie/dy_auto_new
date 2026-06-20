"""Compatibility facade for creative library visual style inference."""

import sys

from app.domains.creative_library import visual_style_inference_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
