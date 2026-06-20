"""Compatibility facade for script pipeline storyboard timing helpers."""

import sys

from app.domains.script_pipeline import storyboard_timing as _domain_module

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
