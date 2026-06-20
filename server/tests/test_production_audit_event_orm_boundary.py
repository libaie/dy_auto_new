import subprocess
import sys
from pathlib import Path

from app.db_models import Base
from app.db_models import ProductionAuditEvent as LegacyProductionAuditEvent


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_production_observability_model_boundary_reexports_audit_event():
    from app.db.models.production_observability import ProductionAuditEvent

    assert ProductionAuditEvent is LegacyProductionAuditEvent
    assert ProductionAuditEvent.metadata is Base.metadata
    assert "production_audit_events" in Base.metadata.tables


def test_production_observability_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.production_observability import ProductionAuditEvent; "
        "assert legacy.ProductionAuditEvent is ProductionAuditEvent; "
        "assert 'production_audit_events' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
