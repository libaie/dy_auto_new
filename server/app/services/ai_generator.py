"""Compatibility facade for AI generation helpers."""

from __future__ import annotations

import sys

from app.domains.model_configuration import ai_generator as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
