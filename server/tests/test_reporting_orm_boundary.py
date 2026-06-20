import subprocess
import sys
from pathlib import Path

from app.db_models import Base, DailyStats as LegacyDailyStats, StatsEvent as LegacyStatsEvent


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_reporting_model_boundary_reexports_stats_models():
    from app.db.models.reporting import DailyStats, StatsEvent

    assert DailyStats is LegacyDailyStats
    assert StatsEvent is LegacyStatsEvent
    assert DailyStats.metadata is Base.metadata
    assert StatsEvent.metadata is Base.metadata
    assert "daily_stats" in Base.metadata.tables
    assert "stats_events" in Base.metadata.tables


def test_reporting_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.reporting import DailyStats, StatsEvent; "
        "assert legacy.DailyStats is DailyStats; "
        "assert legacy.StatsEvent is StatsEvent"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
