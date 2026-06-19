"""Compatibility facade for task management routes.

The implementation now lives in app.domains.task_operations.tasks_router.
Keep this import path until cleanup gates prove no legacy callers remain.
"""

import sys

from app.domains.task_operations import tasks_router as _tasks_router

_LEGACY_MODULE_NAME = __name__
sys.modules[_LEGACY_MODULE_NAME] = _tasks_router
globals().update(_tasks_router.__dict__)
