from __future__ import annotations

import sys

from app.domains.video_production import video_production_readiness as _impl

sys.modules[__name__] = _impl
