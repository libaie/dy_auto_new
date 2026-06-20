"""Compatibility facade for image generation storage helpers."""

import sys

from app.domains.image_generation import image_creation_storage as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
