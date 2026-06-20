"""Compatibility facade for runtime model configuration helpers."""

import sys

from app.domains.model_configuration import runtime_model_config as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
