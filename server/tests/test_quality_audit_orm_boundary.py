import subprocess
import sys
from pathlib import Path

from app.db_models import AuditReport as LegacyAuditReport, Base


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_quality_audit_model_boundary_reexports_audit_report():
    from app.db.models.quality_audit import AuditReport

    assert AuditReport is LegacyAuditReport
    assert AuditReport.metadata is Base.metadata
    assert "audit_reports" in Base.metadata.tables


def test_quality_audit_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.quality_audit import AuditReport; "
        "assert legacy.AuditReport is AuditReport; "
        "assert 'audit_reports' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
