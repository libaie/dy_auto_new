"""SQLAlchemy ORM models — database persistence layer."""

from app.db.base import Base

from app.db.models.ai_text_artifacts import AITextArtifact, AITextArtifactConsumer
from app.db.models.ai_video_series import Episode, Series, series_characters, series_scenes
from app.db.models.agency_operations import AgencyCreativePatch, AgencyExpertInvocation
from app.db.models.account_operations import (
    Account,
    AccountGroup,
    AccountGroupMember,
    ChainInstance,
    ChainTemplate,
    Channel,
    ChannelItem,
)
from app.db.models.device_operations import Device, DevicePairRequest
from app.db.models.content_collection import (
    CollectedComment,
    CollectedUser,
    ContentTemplate,
    Conversation,
    DMSequence,
    RepliedComment,
    SensitiveWord,
)
from app.db.models.creative_library import (
    Character,
    CharacterAnchor,
    ReferenceCategory,
    ReferenceData,
    Scene,
    SceneAnchor,
)
from app.db.models.identity_access import User
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
from app.db.models.model_configuration import AIModel
from app.db.models.prompt_management import PromptTemplate
from app.db.models.production_observability import ProductionAuditEvent
from app.db.models.quality_audit import AuditReport
from app.db.models.reporting import DailyStats, StatsEvent
from app.db.models.script_pipeline import (
    EpisodeScript,
    PipelineRun,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
)
from app.db.models.selector_management import UISelector
from app.db.models.system_configuration import SystemSetting
from app.db.models.task_operations import Task
from app.db.models.video_library import GeneratedVideo
from app.db.models.video_production import (
    ProviderCostReservation,
    ProviderStageTask,
    ProductionCostEvent,
    ProductionEpisode,
    ProductionJob,
    ProductionPlan,
    ProductionPlanVersion,
    ProductionScene,
    ProductionSegment,
    ProductionShot,
    VideoCollection,
    VideoProductionAsset,
    VideoProductionRun,
    VideoReviewRecord,
)
