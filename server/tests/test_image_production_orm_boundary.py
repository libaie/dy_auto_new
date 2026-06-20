import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    ImageSelectionPreview as LegacyImageSelectionPreview,
    ImageProductionPolicyVersion as LegacyImageProductionPolicyVersion,
    ImageProductionStrategy as LegacyImageProductionStrategy,
    ImageProductionStrategyVersion as LegacyImageProductionStrategyVersion,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_image_production_strategy_model_boundary_reexports_models():
    from app.db.models.image_production import (
        ImageSelectionPreview,
        ImageProductionPolicyVersion,
        ImageProductionStrategy,
        ImageProductionStrategyVersion,
    )

    assert ImageSelectionPreview is LegacyImageSelectionPreview
    assert ImageProductionPolicyVersion is LegacyImageProductionPolicyVersion
    assert ImageProductionStrategy is LegacyImageProductionStrategy
    assert ImageProductionStrategyVersion is LegacyImageProductionStrategyVersion
    assert ImageSelectionPreview.metadata is Base.metadata
    assert ImageProductionPolicyVersion.metadata is Base.metadata
    assert ImageProductionStrategy.metadata is Base.metadata
    assert ImageProductionStrategyVersion.metadata is Base.metadata
    assert ImageSelectionPreview.__module__ == "app.db.models.image_production"
    assert ImageProductionPolicyVersion.__module__ == "app.db.models.image_production"
    assert ImageProductionStrategy.__module__ == "app.db.models.image_production"
    assert ImageProductionStrategyVersion.__module__ == "app.db.models.image_production"
    assert "image_selection_previews" in Base.metadata.tables
    assert "image_production_policy_versions" in Base.metadata.tables
    assert "image_production_strategies" in Base.metadata.tables
    assert "image_production_strategy_versions" in Base.metadata.tables


def test_image_production_strategy_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.image_production import ImageSelectionPreview, ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion; "
        "assert legacy.ImageSelectionPreview is ImageSelectionPreview; "
        "assert legacy.ImageProductionPolicyVersion is ImageProductionPolicyVersion; "
        "assert legacy.ImageProductionStrategy is ImageProductionStrategy; "
        "assert legacy.ImageProductionStrategyVersion is ImageProductionStrategyVersion; "
        "assert ImageSelectionPreview.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionPolicyVersion.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionStrategy.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionStrategyVersion.__module__ == 'app.db.models.image_production'; "
        "assert 'image_selection_previews' in legacy.Base.metadata.tables; "
        "assert 'image_production_policy_versions' in legacy.Base.metadata.tables; "
        "assert 'image_production_strategies' in legacy.Base.metadata.tables; "
        "assert 'image_production_strategy_versions' in legacy.Base.metadata.tables"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SERVER_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
