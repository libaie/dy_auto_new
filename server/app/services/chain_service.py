"""Compatibility facade for account operation chain services."""

import sys

from app.domains.account_operations import chain_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
