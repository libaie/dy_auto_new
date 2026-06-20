"""Compatibility facade for video production collection helpers."""

import importlib
import sys


_LEGACY_MODULE_NAME = __name__
_domain_module = importlib.import_module("app.domains.video_production.production_collection_service")
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
