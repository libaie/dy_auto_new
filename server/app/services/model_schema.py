"""Compatibility facade for model configuration schema helpers."""

import sys

from app.domains.model_configuration import model_schema as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
