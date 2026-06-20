"""Compatibility facade for image creation workflow helpers."""

from __future__ import annotations

import sys

# approved image creation service compatibility import: app.services.image_creation_storage
# approved image creation service compatibility import: app.services.image_production_cost_service
from app.domains.image_generation import image_creation_service as _domain_module


_LEGACY_MODULE_NAME = __name__
sys.modules[_domain_module.__name__] = _domain_module
sys.modules[_LEGACY_MODULE_NAME] = _domain_module
globals().update(_domain_module.__dict__)
