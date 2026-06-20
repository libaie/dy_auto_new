import subprocess
import sys
from pathlib import Path

from app.db_models import (
    Base,
    ImageCreationAsset as LegacyImageCreationAsset,
    ImageCreationReviewRecord as LegacyImageCreationReviewRecord,
    ImageCreationTask as LegacyImageCreationTask,
    ImageProductionAbAttempt as LegacyImageProductionAbAttempt,
    ImageProductionAbGroup as LegacyImageProductionAbGroup,
    ImageSelectionPreview as LegacyImageSelectionPreview,
    ImageProductionCostEvent as LegacyImageProductionCostEvent,
    ImageProductionMetric as LegacyImageProductionMetric,
    ImageProductionPolicyVersion as LegacyImageProductionPolicyVersion,
    ImageProductionStrategy as LegacyImageProductionStrategy,
    ImageProductionStrategyVersion as LegacyImageProductionStrategyVersion,
)


SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_image_production_strategy_model_boundary_reexports_models():
    from app.db.models.image_production import (
        ImageCreationAsset,
        ImageCreationReviewRecord,
        ImageCreationTask,
        ImageProductionAbAttempt,
        ImageProductionAbGroup,
        ImageSelectionPreview,
        ImageProductionCostEvent,
        ImageProductionMetric,
        ImageProductionPolicyVersion,
        ImageProductionStrategy,
        ImageProductionStrategyVersion,
    )

    assert ImageCreationAsset is LegacyImageCreationAsset
    assert ImageCreationReviewRecord is LegacyImageCreationReviewRecord
    assert ImageCreationTask is LegacyImageCreationTask
    assert ImageProductionAbAttempt is LegacyImageProductionAbAttempt
    assert ImageProductionAbGroup is LegacyImageProductionAbGroup
    assert ImageSelectionPreview is LegacyImageSelectionPreview
    assert ImageProductionCostEvent is LegacyImageProductionCostEvent
    assert ImageProductionMetric is LegacyImageProductionMetric
    assert ImageProductionPolicyVersion is LegacyImageProductionPolicyVersion
    assert ImageProductionStrategy is LegacyImageProductionStrategy
    assert ImageProductionStrategyVersion is LegacyImageProductionStrategyVersion
    assert ImageCreationAsset.metadata is Base.metadata
    assert ImageCreationReviewRecord.metadata is Base.metadata
    assert ImageCreationTask.metadata is Base.metadata
    assert ImageProductionAbAttempt.metadata is Base.metadata
    assert ImageProductionAbGroup.metadata is Base.metadata
    assert ImageSelectionPreview.metadata is Base.metadata
    assert ImageProductionCostEvent.metadata is Base.metadata
    assert ImageProductionMetric.metadata is Base.metadata
    assert ImageProductionPolicyVersion.metadata is Base.metadata
    assert ImageProductionStrategy.metadata is Base.metadata
    assert ImageProductionStrategyVersion.metadata is Base.metadata
    assert ImageCreationAsset.__module__ == "app.db.models.image_production"
    assert ImageCreationReviewRecord.__module__ == "app.db.models.image_production"
    assert ImageCreationTask.__module__ == "app.db.models.image_production"
    assert ImageProductionAbAttempt.__module__ == "app.db.models.image_production"
    assert ImageProductionAbGroup.__module__ == "app.db.models.image_production"
    assert ImageSelectionPreview.__module__ == "app.db.models.image_production"
    assert ImageProductionCostEvent.__module__ == "app.db.models.image_production"
    assert ImageProductionMetric.__module__ == "app.db.models.image_production"
    assert ImageProductionPolicyVersion.__module__ == "app.db.models.image_production"
    assert ImageProductionStrategy.__module__ == "app.db.models.image_production"
    assert ImageProductionStrategyVersion.__module__ == "app.db.models.image_production"
    assert "image_creation_assets" in Base.metadata.tables
    assert "image_creation_review_records" in Base.metadata.tables
    assert "image_creation_tasks" in Base.metadata.tables
    assert "image_production_ab_attempts" in Base.metadata.tables
    assert "image_production_ab_groups" in Base.metadata.tables
    assert "image_selection_previews" in Base.metadata.tables
    assert "image_production_cost_events" in Base.metadata.tables
    assert "image_production_metrics" in Base.metadata.tables
    assert "image_production_policy_versions" in Base.metadata.tables
    assert "image_production_strategies" in Base.metadata.tables
    assert "image_production_strategy_versions" in Base.metadata.tables


def test_image_production_strategy_model_boundary_imports_in_clean_process():
    code = (
        "import app.db_models as legacy; "
        "from app.db.models.image_production import ImageCreationAsset, ImageCreationReviewRecord, ImageCreationTask, ImageProductionAbAttempt, ImageProductionAbGroup, ImageSelectionPreview, ImageProductionCostEvent, ImageProductionMetric, ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion; "
        "assert legacy.ImageCreationAsset is ImageCreationAsset; "
        "assert legacy.ImageCreationReviewRecord is ImageCreationReviewRecord; "
        "assert legacy.ImageCreationTask is ImageCreationTask; "
        "assert legacy.ImageProductionAbAttempt is ImageProductionAbAttempt; "
        "assert legacy.ImageProductionAbGroup is ImageProductionAbGroup; "
        "assert legacy.ImageSelectionPreview is ImageSelectionPreview; "
        "assert legacy.ImageProductionCostEvent is ImageProductionCostEvent; "
        "assert legacy.ImageProductionMetric is ImageProductionMetric; "
        "assert legacy.ImageProductionPolicyVersion is ImageProductionPolicyVersion; "
        "assert legacy.ImageProductionStrategy is ImageProductionStrategy; "
        "assert legacy.ImageProductionStrategyVersion is ImageProductionStrategyVersion; "
        "assert ImageCreationAsset.__module__ == 'app.db.models.image_production'; "
        "assert ImageCreationReviewRecord.__module__ == 'app.db.models.image_production'; "
        "assert ImageCreationTask.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionAbAttempt.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionAbGroup.__module__ == 'app.db.models.image_production'; "
        "assert ImageSelectionPreview.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionCostEvent.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionMetric.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionPolicyVersion.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionStrategy.__module__ == 'app.db.models.image_production'; "
        "assert ImageProductionStrategyVersion.__module__ == 'app.db.models.image_production'; "
        "assert 'image_creation_assets' in legacy.Base.metadata.tables; "
        "assert 'image_creation_review_records' in legacy.Base.metadata.tables; "
        "assert 'image_creation_tasks' in legacy.Base.metadata.tables; "
        "assert 'image_production_ab_attempts' in legacy.Base.metadata.tables; "
        "assert 'image_production_ab_groups' in legacy.Base.metadata.tables; "
        "assert 'image_selection_previews' in legacy.Base.metadata.tables; "
        "assert 'image_production_cost_events' in legacy.Base.metadata.tables; "
        "assert 'image_production_metrics' in legacy.Base.metadata.tables; "
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
