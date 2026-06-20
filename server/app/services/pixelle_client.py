"""Compatibility facade for Pixelle HTTP client helpers."""

import sys

from app.domains.pixelle_integration import pixelle_client as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
