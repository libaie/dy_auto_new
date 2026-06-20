from __future__ import annotations

import sys

from app.domains.agency_operations import agency_creative_patch_service as _impl

sys.modules[__name__] = _impl
