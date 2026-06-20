from __future__ import annotations

import sys

from app.domains.agency_operations import agency_debate_audit as _impl

sys.modules[__name__] = _impl
