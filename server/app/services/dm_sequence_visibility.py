"""Compatibility facade for DM sequence visibility rules."""

import sys

from app.domains.content_collection import dm_sequence_visibility as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
