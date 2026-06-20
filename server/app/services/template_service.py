"""Compatibility facade for selector template services."""

import sys

from app.domains.selector_management import template_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
