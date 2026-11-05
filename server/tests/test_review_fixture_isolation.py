"""Exercise the shared fixture's real boundary after a seeded account mutates."""
import pytest
from sqlalchemy.orm import sessionmaker

from app.db_models import Account
from app.models import TaskType
from app.services.task_service import task_service
from tests.conftest import _isolate_test


@pytest.mark.parametrize('account_id,status', [('acc-001', 'risk_controlled'), ('acc-002', 'banned')])
def test_shared_isolation_restores_seeded_account_dispatch_baseline(test_db, account_id, status):
    factory = sessionmaker(bind=test_db, autoflush=False)
    with factory() as db:
        account = db.get(Account, account_id)
        account.status = status
        account.daily_limits = {'comments': 0}
        db.commit()
        task_service.create_task(db, TaskType.SEARCH_COMMENT, account_id, {})
        # An inactive account must remain protected within its own test.
        assert task_service.get_pending_task(db, 'fixture-regression-device') is None

    # Invoke exactly the production test fixture boundary, rather than copying
    # its reset algorithm or weakening dispatch to ignore a leaked status.
    boundary = _isolate_test.__wrapped__(test_db)
    next(boundary)
    try:
        with factory() as db:
            task = task_service.create_task(db, TaskType.SEARCH_COMMENT, account_id, {})
            claimed = task_service.get_pending_task(db, 'fixture-regression-device')
            assert claimed is not None and claimed.id == task.id
    finally:
        boundary.close()
