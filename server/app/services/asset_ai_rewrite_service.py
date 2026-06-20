"""Compatibility facade for creative library asset AI rewrite services."""

import sys

from app.domains.creative_library import asset_ai_rewrite_service as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
