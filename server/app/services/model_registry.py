"""Compatibility facade for model configuration registry."""

import sys

from app.domains.model_configuration import model_registry as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
