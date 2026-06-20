"""Compatibility facade for image generation cost event helpers."""

import sys

from app.domains.image_generation import image_production_cost_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
