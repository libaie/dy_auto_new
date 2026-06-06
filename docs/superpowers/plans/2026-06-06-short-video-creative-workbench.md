# Short Video Creative Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a professional short-video creative workbench where experts produce approved, applicable script/storyboard/prompt/edit-manifest patches before Pixelle submission, and multimodal review produces the same patch type after real assets are generated.

**Architecture:** Add a dedicated `AgencyCreativePatch` lifecycle next to existing expert invocations. Expert output creates patch proposals, human workbench actions approve or reject them, server-side services apply approved patches to production data, and Pixelle provider submission is blocked while required patches remain unresolved. Multimodal review reuses the same patch contract with image/video evidence in the expert context.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic V2, pytest, Vue 3, Vite/Vitest, Tailwind CSS, existing Pixelle stage bridge, existing agency expert runtime.

---

## File Structure

- Create `server/app/services/agency_creative_patch_contracts.py`
  - Pydantic enums and validation for creative patch proposals, statuses, and safe apply fields.
- Create `server/app/services/agency_creative_patch_service.py`
  - Extracts proposals from expert invocations, persists patch rows, lists summaries, edits reviewable patches, approves/rejects, applies approved patches, and checks provider preflight blocking.
- Create `server/app/services/agency_multimodal_review.py`
  - Builds multimodal stage contexts from real assets and invokes the existing agency orchestrator.
- Create `server/alembic/versions/2c3d4e5f6071_add_agency_creative_patches.py`
  - Adds `agency_creative_patches`.
- Modify `server/app/db_models.py`
  - Adds `AgencyCreativePatch`.
- Modify `server/tests/conftest.py`
  - Imports and cleans `AgencyCreativePatch`.
- Modify `server/app/services/agency_runtime.py`
  - Allows optional `creative_patches`.
  - Supports multimodal user content for image evidence.
- Modify `server/app/services/agency_prompting.py`
  - Instructs experts to produce `creative_patches`.
  - Creates multimodal message content when evidence images exist.
- Modify `server/app/services/agency_persistence.py`
  - Persists creative patch rows after an invocation completes.
- Modify `server/app/services/agency_console.py`
  - Adds compact creative patch summary and items.
- Modify `server/app/routers/agency.py`
  - Adds creative patch list, edit, approve, reject, apply, apply-approved, and multimodal review endpoints.
- Modify `server/app/services/video_production_service.py`
  - Adds creative patch preflight gates before direct image/video/compose provider submission and real-provider enqueue.
- Modify `server/app/services/production_worker_service.py`
  - Adds creative patch preflight gate before queued worker provider submission.
- Create `server/tests/test_agency_creative_patch_contracts.py`
  - Contract and allowlist tests.
- Create `server/tests/test_agency_creative_patch_service.py`
  - Persistence, target validation, apply behavior, and blocking summary tests.
- Create `server/tests/test_agency_creative_patch_api.py`
  - API lifecycle tests.
- Create `server/tests/test_video_production_creative_patch_gate.py`
  - Direct and worker Pixelle preflight gate tests.
- Create `server/tests/test_agency_multimodal_review.py`
  - Real asset context and multimodal patch proposal tests.
- Modify `server/tests/test_agency_runtime.py`
  - Optional `creative_patches` and multimodal message support tests.
- Modify `server/tests/test_agency_persistence.py`
  - Invocation finalization creates patch rows.
- Create `web/src/components/agency/CreativePatchSummaryStrip.vue`
  - Header summary for pending, applied, rejected, and blocking patches.
- Create `web/src/components/agency/CreativePatchWorkbench.vue`
  - Workbench shell and tabs for patch groups.
- Create `web/src/components/agency/CreativePatchList.vue`
  - Patch list grouped by stage/target.
- Create `web/src/components/agency/CreativePatchDiff.vue`
  - Compact before/after diff and editable `after` form.
- Create `web/src/components/agency/CreativePatchActions.vue`
  - Approve, reject, apply, and source invocation buttons.
- Modify `web/src/api/agency.js`
  - Adds creative patch and multimodal review API clients.
- Modify `web/src/views/AgencyConsolePage.vue`
  - Adds workbench tabs and patch components while preserving expert trace and 3D views.
- Modify `web/src/__tests__/agency-api.test.js`
  - Adds creative patch API expectations.
- Create `web/src/__tests__/creative-patch-workbench.test.js`
  - Component interaction tests.
- Modify `web/src/__tests__/agency-console-page.test.js`
  - Console integration and Chinese copy tests.

---

### Task 1: Creative Patch Contracts

**Files:**
- Create: `server/app/services/agency_creative_patch_contracts.py`
- Test: `server/tests/test_agency_creative_patch_contracts.py`

- [ ] **Step 1: Write the failing contract tests**

```python
import pytest
from pydantic import ValidationError

from app.services.agency_creative_patch_contracts import (
    CreativePatchProposal,
    CreativePatchStatus,
    normalize_patch_payload,
)


def test_storyboard_patch_accepts_only_allowed_after_fields():
    proposal = CreativePatchProposal.model_validate({
        "patch_type": "storyboard_patch",
        "target_type": "storyboard_frame",
        "target_id": "shot-001",
        "stage": "storyboard",
        "title": "强化前三秒钩子",
        "reason": "原分镜缺少可见冲突。",
        "before": {"image_prompt": "原画面", "unsafe": "kept only as before snapshot"},
        "after": {
            "image_prompt": "主角在会议室被当众羞辱，纸张飞散",
            "video_prompt": "纸张砸向镜头后快速推近主角表情",
            "unexpected_column": "blocked",
        },
        "apply_policy": "requires_human_approval",
        "priority": "high",
    })

    normalized = normalize_patch_payload(proposal)

    assert normalized.after == {
        "image_prompt": "主角在会议室被当众羞辱，纸张飞散",
        "video_prompt": "纸张砸向镜头后快速推近主角表情",
    }
    assert normalized.status == CreativePatchStatus.PROPOSED


def test_unknown_patch_type_is_rejected():
    with pytest.raises(ValidationError):
        CreativePatchProposal.model_validate({
            "patch_type": "shell_command_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "storyboard",
            "title": "非法补丁",
            "reason": "不能执行命令。",
            "before": {},
            "after": {},
            "apply_policy": "requires_human_approval",
        })
```

- [ ] **Step 2: Run the contract tests and verify failure**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_contracts.py -q
```

Expected: fails because `agency_creative_patch_contracts.py` does not exist.

- [ ] **Step 3: Implement the contracts**

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class CreativePatchType(StrEnum):
    SCRIPT = "script_patch"
    STORYBOARD = "storyboard_patch"
    IMAGE_PROMPT = "image_prompt_patch"
    VIDEO_PROMPT = "video_prompt_patch"
    EDIT_MANIFEST = "edit_manifest_patch"


class CreativePatchTargetType(StrEnum):
    EPISODE_SCRIPT = "episode_script"
    STORYBOARD_FRAME = "storyboard_frame"
    PRODUCTION_SEGMENT = "production_segment"
    EDIT_MANIFEST = "edit_manifest"


class CreativePatchStatus(StrEnum):
    PROPOSED = "proposed"
    EDITED = "edited"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


class CreativePatchPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


ALLOWED_AFTER_FIELDS: dict[CreativePatchType, set[str]] = {
    CreativePatchType.SCRIPT: {"hook", "beats", "scene_outlines", "visual_shots", "notes"},
    CreativePatchType.STORYBOARD: {
        "image_prompt",
        "video_prompt",
        "narration",
        "duration",
        "action",
        "emotion",
        "shot_type",
        "continuity_notes",
        "reference_urls",
    },
    CreativePatchType.IMAGE_PROMPT: {"image_prompt", "negative_prompt", "reference_instructions"},
    CreativePatchType.VIDEO_PROMPT: {"video_prompt", "duration", "continuity_notes", "expected_end_state"},
    CreativePatchType.EDIT_MANIFEST: {
        "subtitle_style",
        "bgm_policy",
        "intro_outro",
        "watermark",
        "output_spec",
        "rhythm_notes",
    },
}

TARGETS_BY_PATCH_TYPE: dict[CreativePatchType, set[CreativePatchTargetType]] = {
    CreativePatchType.SCRIPT: {CreativePatchTargetType.EPISODE_SCRIPT},
    CreativePatchType.STORYBOARD: {CreativePatchTargetType.STORYBOARD_FRAME},
    CreativePatchType.IMAGE_PROMPT: {CreativePatchTargetType.PRODUCTION_SEGMENT},
    CreativePatchType.VIDEO_PROMPT: {CreativePatchTargetType.PRODUCTION_SEGMENT},
    CreativePatchType.EDIT_MANIFEST: {CreativePatchTargetType.EDIT_MANIFEST},
}


class CreativePatchProposal(BaseModel):
    patch_type: CreativePatchType
    target_type: CreativePatchTargetType
    target_id: str
    stage: str
    title: str
    reason: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    apply_policy: str = "requires_human_approval"
    priority: CreativePatchPriority = CreativePatchPriority.NORMAL
    status: CreativePatchStatus = CreativePatchStatus.PROPOSED

    @field_validator("target_id", "stage", "title", "reason")
    @classmethod
    def non_empty(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("apply_policy")
    @classmethod
    def requires_human_approval(cls, value: str) -> str:
        if value != "requires_human_approval":
            raise ValueError("creative patches require human approval")
        return value

    @model_validator(mode="after")
    def validate_target_matches_patch(self) -> "CreativePatchProposal":
        if self.target_type not in TARGETS_BY_PATCH_TYPE[self.patch_type]:
            raise ValueError("target_type does not match patch_type")
        return self


def normalize_patch_payload(proposal: CreativePatchProposal) -> CreativePatchProposal:
    allowed = ALLOWED_AFTER_FIELDS[proposal.patch_type]
    return proposal.model_copy(update={
        "after": {key: value for key, value in proposal.after.items() if key in allowed},
        "status": CreativePatchStatus.PROPOSED,
    })
```

- [ ] **Step 4: Run the contract tests and verify pass**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_contracts.py -q
```

Expected: passes.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/agency_creative_patch_contracts.py server/tests/test_agency_creative_patch_contracts.py
git commit -m "feat: add agency creative patch contracts"
```

---

### Task 2: Database Model And Migration

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/tests/conftest.py`
- Create: `server/alembic/versions/2c3d4e5f6071_add_agency_creative_patches.py`
- Test: `server/tests/test_agency_creative_patch_service.py`

- [ ] **Step 1: Write the failing model persistence test**

```python
from app.db_models import AgencyCreativePatch, Episode, Series


def test_agency_creative_patch_row_can_be_persisted(db):
    series = Series(title="创作台", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": []})
    db.add(episode)
    db.flush()

    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="强化钩子",
        reason="前三秒缺少冲突。",
        before_json={"image_prompt": "原"},
        after_json={"image_prompt": "新"},
        status="proposed",
        priority="high",
    )
    db.add(patch)
    db.commit()

    stored = db.query(AgencyCreativePatch).filter_by(id=patch.id).one()
    assert stored.series_id == series.id
    assert stored.status == "proposed"
    assert stored.after_json == {"image_prompt": "新"}
```

- [ ] **Step 2: Run the persistence test and verify failure**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_service.py::test_agency_creative_patch_row_can_be_persisted -q
```

Expected: fails because `AgencyCreativePatch` is not defined.

- [ ] **Step 3: Add `AgencyCreativePatch` to `db_models.py`**

Add the class after `AgencyExpertInvocation`:

```python
class AgencyCreativePatch(Base):
    __tablename__ = "agency_creative_patches"
    __table_args__ = (
        Index("idx_agency_creative_patches_series_created", "series_id", "created_at"),
        Index("idx_agency_creative_patches_run_status", "run_id", "status"),
        Index("idx_agency_creative_patches_invocation", "source_invocation_id"),
        Index("idx_agency_creative_patches_target_status", "target_type", "target_id", "status"),
        Index("idx_agency_creative_patches_plan_stage_status", "production_plan_id", "stage", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True)
    run_id = Column(String(36), ForeignKey("video_production_runs.id", ondelete="SET NULL"), nullable=True)
    production_plan_id = Column(String(36), ForeignKey("production_plans.id", ondelete="SET NULL"), nullable=True)
    production_episode_id = Column(String(36), ForeignKey("production_episodes.id", ondelete="SET NULL"), nullable=True)
    production_segment_id = Column(String(36), ForeignKey("production_segments.id", ondelete="SET NULL"), nullable=True)
    source_invocation_id = Column(String(36), ForeignKey("agency_expert_invocations.id", ondelete="SET NULL"), nullable=True)
    stage = Column(String(40), nullable=False)
    expert_id = Column(String(80), nullable=False, default="")
    patch_type = Column(String(40), nullable=False)
    target_type = Column(String(40), nullable=False)
    target_id = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False, default="")
    reason = Column(Text, nullable=False, default="")
    before_json = Column(JSON, nullable=False, default=dict)
    after_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="proposed")
    priority = Column(String(20), nullable=False, default="normal")
    reviewer_user_id = Column(String(36), nullable=True)
    applied_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
```

- [ ] **Step 4: Add the migration**

```python
"""add agency creative patches

Revision ID: 2c3d4e5f6071
Revises: 1b2c3d4e5f60
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa


revision = "2c3d4e5f6071"
down_revision = "1b2c3d4e5f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agency_creative_patches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("series_id", sa.String(length=36), nullable=False),
        sa.Column("episode_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("production_plan_id", sa.String(length=36), nullable=True),
        sa.Column("production_episode_id", sa.String(length=36), nullable=True),
        sa.Column("production_segment_id", sa.String(length=36), nullable=True),
        sa.Column("source_invocation_id", sa.String(length=36), nullable=True),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("expert_id", sa.String(length=80), nullable=False),
        sa.Column("patch_type", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=False),
        sa.Column("after_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_episode_id"], ["production_episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_plan_id"], ["production_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["production_segment_id"], ["production_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["video_production_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_invocation_id"], ["agency_expert_invocations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agency_creative_patches_series_created", "agency_creative_patches", ["series_id", "created_at"])
    op.create_index("idx_agency_creative_patches_run_status", "agency_creative_patches", ["run_id", "status"])
    op.create_index("idx_agency_creative_patches_invocation", "agency_creative_patches", ["source_invocation_id"])
    op.create_index("idx_agency_creative_patches_target_status", "agency_creative_patches", ["target_type", "target_id", "status"])
    op.create_index("idx_agency_creative_patches_plan_stage_status", "agency_creative_patches", ["production_plan_id", "stage", "status"])


def downgrade() -> None:
    op.drop_index("idx_agency_creative_patches_plan_stage_status", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_target_status", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_invocation", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_run_status", table_name="agency_creative_patches")
    op.drop_index("idx_agency_creative_patches_series_created", table_name="agency_creative_patches")
    op.drop_table("agency_creative_patches")
```

- [ ] **Step 5: Add test cleanup**

Modify `server/tests/conftest.py` import list to include `AgencyCreativePatch`, then insert it in `_CLEANUP_TABLES` before `AgencyExpertInvocation`:

```python
VideoReviewRecord, ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion, ImageSelectionPreview, ImageCreationTask, ImageCreationAsset, ImageProductionCostEvent, ImageProductionAbAttempt, ImageProductionAbGroup, ImageProductionMetric, ImageCreationReviewRecord, AgencyCreativePatch, AgencyExpertInvocation, ProductionAuditEvent, ProductionCostEvent, ProductionJob, ProductionSegment, ProductionShot, ProductionScene, ProductionEpisode, ProductionPlanVersion, ProductionPlan, VideoCollection, EpisodeScript, ScriptDramaticBeat, ScriptSceneOutline, ScriptVisualShot, series_characters, series_scenes
```

- [ ] **Step 6: Run model persistence and migration head checks**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_service.py::test_agency_creative_patch_row_can_be_persisted -q
.\.venv\Scripts\python.exe -m alembic heads
```

Expected: persistence test passes, Alembic shows `2c3d4e5f6071 (head)`.

- [ ] **Step 7: Commit**

```powershell
git add server/app/db_models.py server/alembic/versions/2c3d4e5f6071_add_agency_creative_patches.py server/tests/conftest.py server/tests/test_agency_creative_patch_service.py
git commit -m "feat: persist agency creative patches"
```

---

### Task 3: Creative Patch Service

**Files:**
- Create: `server/app/services/agency_creative_patch_service.py`
- Modify: `server/tests/test_agency_creative_patch_service.py`

- [ ] **Step 1: Add failing service tests**

Append these tests:

```python
from app.db_models import AgencyCreativePatch, AgencyExpertInvocation, Episode, ProductionSegment, ProductionShot, ProductionScene, ProductionEpisode, ProductionPlan, Series, VideoProductionRun
from app.services.agency_creative_patch_service import (
    apply_patch,
    create_patches_for_invocation,
    creative_patch_summary,
    unresolved_patch_gate,
)


SOURCE = {
    "source_repo": "jnMetaCode/agency-agents-zh",
    "source_commit": "13b8800",
    "source_path": "specialized/prompt-engineer.md",
    "source_sha256": "a" * 64,
}


def _series_episode_run(db):
    series = Series(title="导演台", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        script_json={"hook": "原钩子"},
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原图", "video_prompt": "原视频"}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="draft",
        current_stage="draft",
        storyboard_json=episode.storyboard_json,
        edit_manifest_json={"subtitle_style": {"position": "bottom"}},
    )
    db.add(run)
    db.flush()
    invocation = AgencyExpertInvocation(
        idempotency_key="creative-patch-test",
        series_id=series.id,
        episode_id=episode.id,
        run_id=run.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        execution_status="completed",
        result_status="warn",
        input_summary_json={},
        output_summary_json={},
        **SOURCE,
    )
    db.add(invocation)
    db.commit()
    return series, episode, run, invocation


def test_create_patches_for_invocation_validates_target_and_persists(db):
    series, episode, run, invocation = _series_episode_run(db)
    output = {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "storyboard",
            "title": "强化钩子",
            "reason": "前三秒不够强。",
            "before": {"image_prompt": "原图"},
            "after": {"image_prompt": "新图", "unexpected": "dropped"},
            "apply_policy": "requires_human_approval",
            "priority": "high",
        }],
    }

    patches = create_patches_for_invocation(db, invocation, output)

    assert len(patches) == 1
    assert patches[0].series_id == series.id
    assert patches[0].run_id == run.id
    assert patches[0].after_json == {"image_prompt": "新图"}
    assert patches[0].status == "proposed"


def test_missing_target_does_not_create_operational_patch(db):
    _, _, _, invocation = _series_episode_run(db)
    output = {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "missing-shot",
            "stage": "storyboard",
            "title": "缺失目标",
            "reason": "目标不存在。",
            "before": {},
            "after": {"image_prompt": "新图"},
            "apply_policy": "requires_human_approval",
        }],
    }

    patches = create_patches_for_invocation(db, invocation, output)

    assert patches == []
    assert db.query(AgencyCreativePatch).count() == 0


def test_apply_storyboard_patch_updates_episode_and_run_storyboard(db):
    _, episode, run, invocation = _series_episode_run(db)
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "storyboard",
            "title": "强化钩子",
            "reason": "前三秒不够强。",
            "before": {"image_prompt": "原图"},
            "after": {"image_prompt": "新图", "video_prompt": "新视频"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "approved"
    db.commit()

    result = apply_patch(db, patch.id, reviewer_user_id="test-user-id")

    db.refresh(episode)
    db.refresh(run)
    assert result["status"] == "applied"
    assert episode.storyboard_json["frames"][0]["image_prompt"] == "新图"
    assert run.storyboard_json["frames"][0]["video_prompt"] == "新视频"


def test_unresolved_patch_gate_blocks_pending_run_patch(db):
    _, _, run, invocation = _series_episode_run(db)
    create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "image_stage",
            "title": "提交前改图",
            "reason": "画面提示词需要先确认。",
            "before": {"image_prompt": "原图"},
            "after": {"image_prompt": "新图"},
            "apply_policy": "requires_human_approval",
        }],
    })

    gate = unresolved_patch_gate(db, run, stage="image_stage")

    assert gate["blocked"] is True
    assert gate["blocking_count"] == 1
    assert gate["repair_route"] == f"/series/{run.series_id}/agency-console?tab=workbench"


def test_summary_counts_patch_statuses(db):
    _, _, run, invocation = _series_episode_run(db)
    patch = create_patches_for_invocation(db, invocation, {
        "creative_patches": [{
            "patch_type": "storyboard_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "image_stage",
            "title": "提交前改图",
            "reason": "画面提示词需要先确认。",
            "before": {},
            "after": {"image_prompt": "新图"},
            "apply_policy": "requires_human_approval",
        }],
    })[0]
    patch.status = "rejected"
    db.commit()

    summary = creative_patch_summary(db, series_id=run.series_id, run_id=run.id)

    assert summary["total"] == 1
    assert summary["rejected"] == 1
    assert summary["blocking"] == 0
```

- [ ] **Step 2: Run the service tests and verify failure**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_service.py -q
```

Expected: fails because `agency_creative_patch_service.py` does not exist.

- [ ] **Step 3: Implement `agency_creative_patch_service.py`**

Implement these public functions with the exact names used by tests:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.db_models import AgencyCreativePatch, AgencyExpertInvocation, Episode, ProductionAuditEvent, ProductionSegment, VideoProductionRun
from app.services.agency_creative_patch_contracts import CreativePatchProposal, normalize_patch_payload

BLOCKING_STATUSES = {"proposed", "edited", "approved"}
PATCH_STATUS_COUNTS = ("proposed", "edited", "approved", "applied", "rejected")


def create_patches_for_invocation(db: Session, invocation: AgencyExpertInvocation, output_summary: dict[str, Any]) -> list[AgencyCreativePatch]:
    created: list[AgencyCreativePatch] = []
    for raw in output_summary.get("creative_patches") or []:
        if not isinstance(raw, dict):
            _record_invalid_patch(db, invocation, "补丁不是 JSON 对象", raw)
            continue
        try:
            proposal = normalize_patch_payload(CreativePatchProposal.model_validate(raw))
        except Exception as exc:
            _record_invalid_patch(db, invocation, str(exc), raw)
            continue
        if not _target_exists(db, invocation, proposal.target_type.value, proposal.target_id):
            _record_invalid_patch(db, invocation, "补丁目标不存在或不属于当前生产范围", raw)
            continue
        patch = AgencyCreativePatch(
            series_id=invocation.series_id,
            episode_id=invocation.episode_id,
            run_id=invocation.run_id,
            production_plan_id=invocation.production_plan_id,
            production_episode_id=invocation.production_episode_id,
            production_segment_id=invocation.production_segment_id if proposal.target_type.value == "production_segment" else None,
            source_invocation_id=invocation.id,
            stage=proposal.stage,
            expert_id=invocation.expert_id,
            patch_type=proposal.patch_type.value,
            target_type=proposal.target_type.value,
            target_id=proposal.target_id,
            title=proposal.title,
            reason=proposal.reason,
            before_json=proposal.before,
            after_json=proposal.after,
            status=proposal.status.value,
            priority=proposal.priority.value,
        )
        db.add(patch)
        db.flush()
        created.append(patch)
        _record_patch_event(db, "agency_creative_patch.created", patch, {"source_invocation_id": invocation.id})
    return created
```

Implement helpers in the same file:

```python
def _target_exists(db: Session, invocation: AgencyExpertInvocation, target_type: str, target_id: str) -> bool:
    if target_type == "episode_script":
        return bool(invocation.episode_id and target_id in {invocation.episode_id, "episode_script", "script"})
    if target_type == "storyboard_frame":
        episode = db.query(Episode).filter(Episode.id == invocation.episode_id).first() if invocation.episode_id else None
        run = db.query(VideoProductionRun).filter(VideoProductionRun.id == invocation.run_id).first() if invocation.run_id else None
        return _frame_index((episode.storyboard_json if episode else None) or {}, target_id) is not None or _frame_index((run.storyboard_json if run else None) or {}, target_id) is not None
    if target_type == "production_segment":
        query = db.query(ProductionSegment).filter(ProductionSegment.id == target_id)
        if invocation.production_segment_id:
            query = query.filter(ProductionSegment.id == invocation.production_segment_id)
        return query.first() is not None
    if target_type == "edit_manifest":
        return bool(invocation.run_id and target_id in {invocation.run_id, "edit_manifest", "compose"})
    return False


def _frame_index(storyboard: dict, target_id: str) -> int | None:
    frames = storyboard.get("frames") or []
    for index, frame in enumerate(frames):
        if str(frame.get("frame_id") or frame.get("shot_id") or "") == target_id:
            return index
    return None


def _record_invalid_patch(db: Session, invocation: AgencyExpertInvocation, reason: str, raw: Any) -> None:
    db.add(ProductionAuditEvent(
        event_type="agency_creative_patch.invalid",
        run_id=invocation.run_id,
        production_plan_id=invocation.production_plan_id,
        production_episode_id=invocation.production_episode_id,
        production_segment_id=invocation.production_segment_id,
        payload_json={
            "invocation_id": invocation.id,
            "reason": reason,
            "raw_patch": raw if isinstance(raw, dict) else str(raw),
        },
    ))


def _record_patch_event(db: Session, event_type: str, patch: AgencyCreativePatch, payload: dict[str, Any] | None = None) -> None:
    db.add(ProductionAuditEvent(
        event_type=event_type,
        run_id=patch.run_id,
        production_plan_id=patch.production_plan_id,
        production_episode_id=patch.production_episode_id,
        production_segment_id=patch.production_segment_id,
        payload_json={"patch_id": patch.id, **(payload or {})},
    ))
```

Implement lifecycle functions in the same file:

```python
def creative_patch_summary(db: Session, *, series_id: str | None = None, run_id: str | None = None) -> dict[str, int]:
    query = db.query(AgencyCreativePatch)
    if series_id:
        query = query.filter(AgencyCreativePatch.series_id == series_id)
    if run_id:
        query = query.filter(AgencyCreativePatch.run_id == run_id)
    rows = query.all()
    summary = {"total": len(rows), "blocking": 0}
    for status in PATCH_STATUS_COUNTS:
        summary[status] = 0
    for row in rows:
        if row.status in summary:
            summary[row.status] += 1
        if row.status in {"proposed", "edited", "approved"}:
            summary["blocking"] += 1
    return summary


def unresolved_patch_gate(db: Session, run: VideoProductionRun, *, stage: str) -> dict[str, Any]:
    rows = (
        db.query(AgencyCreativePatch)
        .filter(AgencyCreativePatch.run_id == run.id)
        .filter(AgencyCreativePatch.stage == stage)
        .filter(AgencyCreativePatch.status.in_(list(BLOCKING_STATUSES)))
        .all()
    )
    return {
        "blocked": bool(rows),
        "blocking_count": len(rows),
        "patch_ids": [row.id for row in rows],
        "repair_action": "打开短视频导演台处理专家改稿补丁",
        "repair_route": f"/series/{run.series_id}/agency-console?tab=workbench",
    }
```

Implement `update_patch_after`, `approve_patch`, `reject_patch`, and `apply_patch`. `apply_patch` should call type-specific private functions:

```python
def apply_patch(db: Session, patch_id: str, *, reviewer_user_id: str | None = None) -> dict[str, Any]:
    patch = db.query(AgencyCreativePatch).filter(AgencyCreativePatch.id == patch_id).first()
    if not patch:
        raise ValueError("creative patch not found")
    if patch.status == "applied":
        return {"id": patch.id, "status": patch.status}
    if patch.status != "approved":
        raise ValueError("creative patch must be approved before apply")
    if patch.patch_type == "storyboard_patch":
        _apply_storyboard_patch(db, patch)
    elif patch.patch_type == "script_patch":
        _apply_script_patch(db, patch)
    elif patch.patch_type in {"image_prompt_patch", "video_prompt_patch"}:
        _apply_segment_prompt_patch(db, patch)
    elif patch.patch_type == "edit_manifest_patch":
        _apply_edit_manifest_patch(db, patch)
    else:
        raise ValueError("unsupported creative patch type")
    patch.status = "applied"
    patch.reviewer_user_id = reviewer_user_id
    patch.applied_at = bj_now()
    _record_patch_event(db, "agency_creative_patch.applied", patch, {"reviewer_user_id": reviewer_user_id})
    db.commit()
    db.refresh(patch)
    return {"id": patch.id, "status": patch.status}
```

For `_apply_storyboard_patch`, update both `Episode.storyboard_json.frames` and `VideoProductionRun.storyboard_json.frames` when present.

- [ ] **Step 4: Run the service tests and verify pass**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_service.py -q
```

Expected: passes.

- [ ] **Step 5: Commit**

```powershell
git add server/app/services/agency_creative_patch_service.py server/tests/test_agency_creative_patch_service.py
git commit -m "feat: apply agency creative patches"
```

---

### Task 4: Runtime, Prompting, And Persistence Integration

**Files:**
- Modify: `server/app/services/agency_runtime.py`
- Modify: `server/app/services/agency_prompting.py`
- Modify: `server/app/services/agency_persistence.py`
- Modify: `server/tests/test_agency_runtime.py`
- Modify: `server/tests/test_agency_persistence.py`

- [ ] **Step 1: Add failing runtime and persistence tests**

Add to `server/tests/test_agency_runtime.py`:

```python
@pytest.mark.asyncio
async def test_runtime_preserves_optional_creative_patches():
    async def fake_client(system_prompt, user_prompt, config):
        return _valid_output(
            decision="需要改稿",
            creative_patches=[{
                "patch_type": "storyboard_patch",
                "target_type": "storyboard_frame",
                "target_id": "shot-001",
                "stage": "storyboard",
                "title": "强化前三秒钩子",
                "reason": "冲突不够强。",
                "before": {"image_prompt": "原"},
                "after": {"image_prompt": "新"},
                "apply_policy": "requires_human_approval",
            }],
        )

    runtime = AgencySkillRuntime(model_client=fake_client)
    result = await runtime.invoke(
        db=None,
        expert_id="prompt_engineer",
        stage="storyboard",
        role="reviewer",
        stage_context={"frame_count": 1},
        runtime_config=_runtime_config(),
    )

    assert result.output_summary["creative_patches"][0]["patch_type"] == "storyboard_patch"
```

Add to `server/tests/test_agency_persistence.py`:

```python
def test_finalize_invocation_creates_creative_patch_rows(db):
    series = _series(db)
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原"}]},
    )
    db.add(episode)
    db.commit()
    invocation = create_or_resume_invocation(
        db,
        idempotency_key="creative-patch-finalize",
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        role="reviewer",
        source=SOURCE,
        input_summary={},
    )

    finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="warn",
        output_summary={
            "decision": "需要改稿",
            "creative_patches": [{
                "patch_type": "storyboard_patch",
                "target_type": "storyboard_frame",
                "target_id": "shot-001",
                "stage": "storyboard",
                "title": "强化钩子",
                "reason": "前三秒弱。",
                "before": {"image_prompt": "原"},
                "after": {"image_prompt": "新"},
                "apply_policy": "requires_human_approval",
            }],
        },
        evidence=[],
    )

    patch = db.query(AgencyCreativePatch).one()
    assert patch.source_invocation_id == invocation.id
    assert patch.status == "proposed"
```

Import `Episode` and `AgencyCreativePatch` in that test file.

- [ ] **Step 2: Run the targeted tests and verify failure**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_runtime.py::test_runtime_preserves_optional_creative_patches tests/test_agency_persistence.py::test_finalize_invocation_creates_creative_patch_rows -q
```

Expected: runtime output drops `creative_patches`, persistence does not create rows.

- [ ] **Step 3: Extend `agency_runtime.py`**

Add optional schema property:

```python
"creative_patches": {"type": "array"},
```

Then include it in `output_summary` only when present:

```python
output_summary = {
    "decision": _redact_secrets(parsed["decision"], secret_values),
    "findings": _redact_secrets(parsed["findings"], secret_values),
    "recommendations": _redact_secrets(parsed["recommendations"], secret_values),
    "required_changes": _redact_secrets(parsed["required_changes"], secret_values),
}
if isinstance(parsed.get("creative_patches"), list):
    output_summary["creative_patches"] = _redact_secrets(parsed["creative_patches"], secret_values)
```

Return `output_summary=output_summary`.

- [ ] **Step 4: Extend `agency_prompting.py`**

Add system prompt rules:

```python
"6. When you can improve the production content, put concrete rewrites in creative_patches instead of only writing recommendations.",
"7. creative_patches must use known target ids from context and only update script, storyboard, image prompt, video prompt, or edit manifest fields.",
"8. Every creative patch requires human approval; never claim it has already been applied.",
```

Add the patch schema to the output schema description already passed from runtime.

- [ ] **Step 5: Extend `agency_persistence.py`**

Import and call:

```python
from app.services.agency_creative_patch_service import create_patches_for_invocation
```

After `invocation.output_summary_json = output`, call:

```python
creative_patches = create_patches_for_invocation(db, invocation, output)
```

Add `creative_patch_ids` to the audit payload:

```python
"creative_patch_ids": [patch.id for patch in creative_patches],
```

- [ ] **Step 6: Run targeted tests and verify pass**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_runtime.py::test_runtime_preserves_optional_creative_patches tests/test_agency_persistence.py::test_finalize_invocation_creates_creative_patch_rows -q
```

Expected: passes.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/agency_runtime.py server/app/services/agency_prompting.py server/app/services/agency_persistence.py server/tests/test_agency_runtime.py server/tests/test_agency_persistence.py
git commit -m "feat: persist expert creative patch output"
```

---

### Task 5: Creative Patch API And Console Payload

**Files:**
- Modify: `server/app/routers/agency.py`
- Modify: `server/app/services/agency_console.py`
- Create: `server/tests/test_agency_creative_patch_api.py`
- Modify: `server/tests/test_agency_console.py`

- [ ] **Step 1: Write failing API tests**

```python
from fastapi.testclient import TestClient

from app.db_models import AgencyCreativePatch, Episode, Series
from app.main import app

client = TestClient(app)


def _patch(db):
    series = Series(title="导演台 API", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": [{"frame_id": "shot-001"}]})
    db.add(episode)
    db.flush()
    patch = AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        stage="storyboard",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="强化钩子",
        reason="前三秒弱。",
        before_json={"image_prompt": "原"},
        after_json={"image_prompt": "新"},
        status="proposed",
        priority="high",
    )
    db.add(patch)
    db.commit()
    return series, episode, patch


def test_list_creative_patches_returns_summary_and_items(db):
    series, _, patch = _patch(db)

    response = client.get("/api/agency/creative-patches", params={"series_id": series.id})

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["blocking"] == 1
    assert data["items"][0]["id"] == patch.id
    assert data["items"][0]["after"] == {"image_prompt": "新"}


def test_update_approve_reject_and_apply_lifecycle(db):
    _, _, patch = _patch(db)

    update = client.patch(f"/api/agency/creative-patches/{patch.id}", json={"after": {"image_prompt": "人工改后"}})
    assert update.status_code == 200
    assert update.json()["status"] == "edited"

    approve = client.post(f"/api/agency/creative-patches/{patch.id}/approve")
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    apply = client.post(f"/api/agency/creative-patches/{patch.id}/apply")
    assert apply.status_code == 200
    assert apply.json()["status"] == "applied"
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_api.py -q
```

Expected: fails with 404 for creative patch endpoints.

- [ ] **Step 3: Add serializer and routes in `agency.py`**

Add import:

```python
from app.db_models import AgencyCreativePatch
from app.services.agency_creative_patch_service import apply_patch, approve_patch, creative_patch_summary, reject_patch, update_patch_after
```

Add serializer:

```python
def _creative_patch_item(row: AgencyCreativePatch) -> dict:
    return {
        "id": row.id,
        "series_id": row.series_id,
        "episode_id": row.episode_id,
        "run_id": row.run_id,
        "stage": row.stage,
        "expert_id": row.expert_id,
        "patch_type": row.patch_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "title": row.title,
        "reason": row.reason,
        "before": row.before_json or {},
        "after": row.after_json or {},
        "status": row.status,
        "priority": row.priority,
        "source_invocation_id": row.source_invocation_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
```

Add routes:

```python
@router.get("/creative-patches")
def list_creative_patches(
    series_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    query = db.query(AgencyCreativePatch)
    if series_id:
        query = query.filter(AgencyCreativePatch.series_id == series_id)
    if run_id:
        query = query.filter(AgencyCreativePatch.run_id == run_id)
    if status:
        query = query.filter(AgencyCreativePatch.status == status)
    if stage:
        query = query.filter(AgencyCreativePatch.stage == stage)
    if target_type:
        query = query.filter(AgencyCreativePatch.target_type == target_type)
    if target_id:
        query = query.filter(AgencyCreativePatch.target_id == target_id)
    rows = query.order_by(AgencyCreativePatch.created_at.desc(), AgencyCreativePatch.id.desc()).all()
    return {"summary": creative_patch_summary(db, series_id=series_id, run_id=run_id), "items": [_creative_patch_item(row) for row in rows]}
```

Add `PATCH`, `approve`, `reject`, `apply`, and `apply-approved` endpoints using service functions and returning serialized rows or result dicts.

- [ ] **Step 4: Extend `agency_console.py`**

Import:

```python
from app.services.agency_creative_patch_service import creative_patch_summary
from app.db_models import AgencyCreativePatch
```

Add compact loader:

```python
def _creative_patch_items(db: Session, series: Series, latest_run) -> list[dict]:
    query = db.query(AgencyCreativePatch).filter(AgencyCreativePatch.series_id == series.id)
    if latest_run and hasattr(latest_run, "id"):
        query = query.filter(AgencyCreativePatch.run_id == latest_run.id)
    rows = query.order_by(AgencyCreativePatch.created_at.desc()).limit(20).all()
    return [{
        "id": row.id,
        "stage": row.stage,
        "patch_type": row.patch_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "title": row.title,
        "status": row.status,
        "priority": row.priority,
    } for row in rows]
```

Add to payload:

```python
"creative_patch_summary": creative_patch_summary(db, series_id=series.id, run_id=(latest_run.id if latest_run else None)),
"creative_patches": _creative_patch_items(db, series, latest_run),
```

- [ ] **Step 5: Run API and console tests**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_creative_patch_api.py tests/test_agency_console.py -q
```

Expected: passes.

- [ ] **Step 6: Commit**

```powershell
git add server/app/routers/agency.py server/app/services/agency_console.py server/tests/test_agency_creative_patch_api.py server/tests/test_agency_console.py
git commit -m "feat: expose creative patch workbench API"
```

---

### Task 6: Pixelle Preflight Gates

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/production_worker_service.py`
- Create: `server/tests/test_video_production_creative_patch_gate.py`

- [ ] **Step 1: Write failing preflight gate tests**

```python
import pytest

from app.db_models import AgencyCreativePatch, Episode, Series, VideoProductionRun
from app.services.video_production_service import VideoProductionError, start_image_stage


@pytest.mark.asyncio
async def test_start_image_stage_blocks_pending_creative_patch(db):
    series = Series(title="Gate", logline="Test", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.flush()
    db.add(AgencyCreativePatch(
        series_id=series.id,
        episode_id=episode.id,
        run_id=run.id,
        stage="image_stage",
        expert_id="prompt_engineer",
        patch_type="storyboard_patch",
        target_type="storyboard_frame",
        target_id="shot-001",
        title="提交前改稿",
        reason="画面需要先确认。",
        before_json={},
        after_json={"image_prompt": "新"},
        status="proposed",
        priority="high",
    ))
    db.commit()

    with pytest.raises(VideoProductionError) as exc_info:
        await start_image_stage(db, run.id)

    assert "短视频导演台" in str(exc_info.value) or "creative patch" in str(exc_info.value)
    db.refresh(run)
    assert run.current_stage == "creative_review"
```

- [ ] **Step 2: Run the preflight test and verify failure**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_video_production_creative_patch_gate.py -q
```

Expected: fails because pending creative patches do not block image stage.

- [ ] **Step 3: Add gate helper in `video_production_service.py`**

Import:

```python
from app.services.agency_creative_patch_service import unresolved_patch_gate
```

Add helper:

```python
def _guard_creative_patches(db: Session, run: VideoProductionRun, stage: str) -> None:
    gate = unresolved_patch_gate(db, run, stage=stage)
    if not gate.get("blocked"):
        return
    run.status = "creative_review_required"
    run.current_stage = "creative_review"
    run.updated_at = bj_now()
    _record_run_event(
        db,
        run,
        "agency_creative_patch_gate_blocked",
        payload={"stage": stage, **gate},
    )
    db.commit()
    raise VideoProductionError(
        f"短视频导演台还有 {gate['blocking_count']} 个专家改稿补丁待处理，不能提交 Pixelle。"
    )
```

Call it:

```python
_guard_creative_patches(db, run, "image_stage")
```

before `frames = image_stage_frames(run, db=db)` in `start_image_stage()`.

Call:

```python
_guard_creative_patches(db, run, "video_stage")
```

before `frames = video_stage_frames(db, run)` in `start_video_stage()`.

Call:

```python
_guard_creative_patches(db, run, "compose_preflight")
```

before `segments = compose_segments(db, run)` in `start_compose_stage()`.

Call matching gates inside `start_real_provider_stage_via_executor()` before enqueueing jobs:

```python
if normalized_stage == "image_generation":
    _guard_creative_patches(db, run, "image_stage")
elif normalized_stage == "video_generation":
    _guard_creative_patches(db, run, "video_stage")
elif normalized_stage == "episode_compose":
    _guard_creative_patches(db, run, "compose_preflight")
```

- [ ] **Step 4: Add worker gate**

In `production_worker_service.py`, import `unresolved_patch_gate`.

Before building or submitting a worker job payload in `_job_spec`, check:

```python
stage_gate = {
    "image_generation": "image_stage",
    "video_generation": "video_stage",
    "episode_compose": "compose_preflight",
    "composition": "compose_preflight",
}.get(job.stage)
if stage_gate:
    gate = unresolved_patch_gate(db, run, stage=stage_gate)
    if gate.get("blocked"):
        raise ProductionRepairableError(
            code=ProductionErrorCode.REVIEW_GATE_BLOCKED,
            message=f"短视频导演台还有 {gate['blocking_count']} 个专家改稿补丁待处理。",
            cause="creative_patch_gate_blocked",
            repair_action=gate["repair_action"],
            repair_route=gate["repair_route"],
            retryable=False,
            affected_ids=gate["patch_ids"],
        )
```

- [ ] **Step 5: Add applied/rejected non-blocking tests**

Add tests that set patch status to `applied` and `rejected`, monkeypatch provider calls, and verify submission proceeds to the existing next validation rather than the creative gate.

- [ ] **Step 6: Run targeted tests**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_video_production_creative_patch_gate.py tests/test_video_production_linked_stage_execution.py tests/test_video_production_final_gate.py -q
```

Expected: passes.

- [ ] **Step 7: Commit**

```powershell
git add server/app/services/video_production_service.py server/app/services/production_worker_service.py server/tests/test_video_production_creative_patch_gate.py
git commit -m "feat: block pixelle submission on unresolved creative patches"
```

---

### Task 7: Multimodal Review Context

**Files:**
- Create: `server/app/services/agency_multimodal_review.py`
- Modify: `server/app/services/agency_prompting.py`
- Modify: `server/app/services/agency_runtime.py`
- Modify: `server/app/routers/agency.py`
- Create: `server/tests/test_agency_multimodal_review.py`
- Modify: `server/tests/test_agency_runtime.py`

- [ ] **Step 1: Add failing multimodal runtime test**

Add to `server/tests/test_agency_runtime.py`:

```python
@pytest.mark.asyncio
async def test_runtime_can_send_multimodal_user_content():
    captured = {}

    async def fake_client(system_prompt, user_prompt, config):
        captured["user_prompt"] = user_prompt
        return _valid_output(decision="看图后建议重绘")

    runtime = AgencySkillRuntime(model_client=fake_client)
    await runtime.invoke(
        db=None,
        expert_id="image_review_quality_reviewer",
        stage="image_review",
        role="qa",
        stage_context={
            "asset_review": {
                "media_inputs": [{"type": "image_url", "url": "https://cdn.test/shot.png"}],
                "prompt": "原图像提示词",
            }
        },
        runtime_config=_runtime_config(),
    )

    assert "https://cdn.test/shot.png" in str(captured["user_prompt"])
```

This first test verifies the context reaches the client. A second test in the implementation should verify the default OpenAI-compatible client sends `content` parts when `user_prompt` is a list.

- [ ] **Step 2: Add multimodal review service tests**

```python
import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.services.agency_multimodal_review import build_multimodal_asset_context


def test_build_multimodal_asset_context_includes_real_asset_and_prompt(db):
    series = Series(title="多模态", logline="一句话", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, storyboard_json={"frames": [{"frame_id": "shot-001", "image_prompt": "原图"}]})
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, storyboard_json=episode.storyboard_json)
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="shot-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/shot.png",
        status="review_pending",
        version=1,
    )
    db.add(asset)
    db.commit()

    context = build_multimodal_asset_context(db, asset.id)

    assert context["asset"]["url"] == "https://cdn.test/shot.png"
    assert context["asset_review"]["media_inputs"] == [{"type": "image_url", "url": "https://cdn.test/shot.png"}]
    assert context["storyboard_frame"]["image_prompt"] == "原图"
```

- [ ] **Step 3: Implement prompt multimodal content**

Change `ExpertPrompt` in `agency_prompting.py`:

```python
@dataclass(frozen=True)
class ExpertPrompt:
    system_prompt: str
    user_prompt: str | list[dict[str, Any]]
```

Add:

```python
def _media_inputs(stage_context: dict[str, Any]) -> list[dict[str, Any]]:
    asset_review = stage_context.get("asset_review")
    if not isinstance(asset_review, dict):
        return []
    return [item for item in asset_review.get("media_inputs") or [] if isinstance(item, dict)]
```

Build user content:

```python
user_json = json.dumps({...}, ensure_ascii=False, indent=2)
media_inputs = _media_inputs(stage_context)
if media_inputs:
    content: list[dict[str, Any]] = [{"type": "text", "text": user_json}]
    for media in media_inputs:
        if media.get("type") == "image_url" and media.get("url"):
            content.append({"type": "image_url", "image_url": {"url": media["url"]}})
    user_prompt = content
else:
    user_prompt = user_json
```

- [ ] **Step 4: Implement runtime content support**

Change type aliases:

```python
MessageContent = str | list[dict[str, Any]]
ModelClient = Callable[[str, MessageContent, dict[str, Any]], Awaitable[ModelClientResponse]]
```

In `_default_model_client`, send:

```python
{"role": "user", "content": user_prompt}
```

where `user_prompt` may be string or content parts. Keep fake client tests compatible because `str(user_prompt)` contains the URL.

- [ ] **Step 5: Implement `agency_multimodal_review.py`**

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db_models import Episode, VideoProductionAsset, VideoProductionRun


def build_multimodal_asset_context(db: Session, asset_id: str) -> dict[str, Any]:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise ValueError("asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    episode = db.query(Episode).filter(Episode.id == asset.episode_id).first()
    storyboard = (run.storyboard_json if run else None) or (episode.storyboard_json if episode else None) or {}
    frame = _frame_by_id(storyboard, asset.frame_id)
    media_inputs = []
    if asset.asset_type == "image" and asset.url:
        media_inputs.append({"type": "image_url", "url": asset.url})
    thumbnail_url = (asset.metadata_json or {}).get("thumbnail_url") if asset.metadata_json else None
    if thumbnail_url:
        media_inputs.append({"type": "image_url", "url": thumbnail_url})
    return {
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "asset": {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "stage": asset.stage,
            "url": asset.url,
            "frame_id": asset.frame_id,
            "status": asset.status,
            "version": asset.version,
        },
        "storyboard_frame": frame,
        "asset_review": {
            "media_inputs": media_inputs,
            "original_prompt": frame.get("image_prompt") if asset.asset_type == "image" else frame.get("video_prompt"),
            "review_instruction": "请基于真实素材判断人物一致性、画面冲击力、镜头节奏和抖音短视频质感，并用 creative_patches 给出可执行返修。",
        },
    }


def _frame_by_id(storyboard: dict[str, Any], frame_id: str) -> dict[str, Any]:
    for frame in storyboard.get("frames") or []:
        if str(frame.get("frame_id") or frame.get("shot_id") or "") == frame_id:
            return frame
    return {}
```

Add `run_multimodal_asset_review(db, asset_id, runtime_config)` that uses `AgencyOrchestrator().run_image_review(...)` for images and `run_video_review(...)` for videos.

- [ ] **Step 6: Add API endpoint**

In `agency.py`:

```python
@router.post("/assets/{asset_id}/multimodal-review")
async def run_asset_multimodal_review(asset_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    from app.services.agency_multimodal_review import run_multimodal_asset_review
    trace = await run_multimodal_asset_review(db, asset_id)
    return {"ok": True, "trace": trace}
```

- [ ] **Step 7: Run multimodal tests**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest tests/test_agency_multimodal_review.py tests/test_agency_runtime.py -q
```

Expected: passes.

- [ ] **Step 8: Commit**

```powershell
git add server/app/services/agency_multimodal_review.py server/app/services/agency_prompting.py server/app/services/agency_runtime.py server/app/routers/agency.py server/tests/test_agency_multimodal_review.py server/tests/test_agency_runtime.py
git commit -m "feat: add multimodal creative patch review context"
```

---

### Task 8: Frontend API Clients

**Files:**
- Modify: `web/src/api/agency.js`
- Modify: `web/src/__tests__/agency-api.test.js`

- [ ] **Step 1: Add failing API client tests**

Append:

```javascript
  it('manages creative patch APIs', async () => {
    const {
      listAgencyCreativePatches,
      updateAgencyCreativePatch,
      approveAgencyCreativePatch,
      rejectAgencyCreativePatch,
      applyAgencyCreativePatch,
      applyApprovedAgencyCreativePatches,
      runAgencyAssetMultimodalReview,
    } = await import('../api/agency.js')

    await listAgencyCreativePatches({ series_id: 'sid' })
    await updateAgencyCreativePatch('patch-1', { after: { image_prompt: '新版' } })
    await approveAgencyCreativePatch('patch-1')
    await rejectAgencyCreativePatch('patch-1', { reason: '不采用' })
    await applyAgencyCreativePatch('patch-1')
    await applyApprovedAgencyCreativePatches({ run_id: 'run-1' })
    await runAgencyAssetMultimodalReview('asset-1')

    expect(mockGet).toHaveBeenCalledWith('/agency/creative-patches', { params: { series_id: 'sid' } })
    expect(mockPatch).toHaveBeenCalledWith('/agency/creative-patches/patch-1', { after: { image_prompt: '新版' } })
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/patch-1/approve')
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/patch-1/reject', { reason: '不采用' })
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/patch-1/apply')
    expect(mockPost).toHaveBeenCalledWith('/agency/creative-patches/apply-approved', { run_id: 'run-1' })
    expect(mockPost).toHaveBeenCalledWith('/agency/assets/asset-1/multimodal-review')
  })
```

Update the mock client in the test:

```javascript
const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPatch = vi.fn()

vi.mock('../api/client.js', () => ({
  default: { get: mockGet, post: mockPost, patch: mockPatch },
}))
```

- [ ] **Step 2: Run API test and verify failure**

Run:

```powershell
cd web
npm exec vitest -- src/__tests__/agency-api.test.js --run
```

Expected: fails because functions are missing.

- [ ] **Step 3: Add API client functions**

In `web/src/api/agency.js`:

```javascript
export function listAgencyCreativePatches(params = {}) {
  return client.get('/agency/creative-patches', { params })
}

export function updateAgencyCreativePatch(patchId, payload) {
  return client.patch(`/agency/creative-patches/${patchId}`, payload)
}

export function approveAgencyCreativePatch(patchId) {
  return client.post(`/agency/creative-patches/${patchId}/approve`)
}

export function rejectAgencyCreativePatch(patchId, payload) {
  return client.post(`/agency/creative-patches/${patchId}/reject`, payload)
}

export function applyAgencyCreativePatch(patchId) {
  return client.post(`/agency/creative-patches/${patchId}/apply`)
}

export function applyApprovedAgencyCreativePatches(payload) {
  return client.post('/agency/creative-patches/apply-approved', payload)
}

export function runAgencyAssetMultimodalReview(assetId) {
  return client.post(`/agency/assets/${assetId}/multimodal-review`)
}
```

- [ ] **Step 4: Run API test**

Run:

```powershell
cd web
npm exec vitest -- src/__tests__/agency-api.test.js --run
```

Expected: passes.

- [ ] **Step 5: Commit**

```powershell
git add web/src/api/agency.js web/src/__tests__/agency-api.test.js
git commit -m "feat: add creative patch frontend API"
```

---

### Task 9: Frontend Workbench Components

**Files:**
- Create: `web/src/components/agency/CreativePatchSummaryStrip.vue`
- Create: `web/src/components/agency/CreativePatchWorkbench.vue`
- Create: `web/src/components/agency/CreativePatchList.vue`
- Create: `web/src/components/agency/CreativePatchDiff.vue`
- Create: `web/src/components/agency/CreativePatchActions.vue`
- Create: `web/src/__tests__/creative-patch-workbench.test.js`

- [ ] **Step 1: Write failing component tests**

```javascript
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CreativePatchWorkbench from '../components/agency/CreativePatchWorkbench.vue'

const patches = [{
  id: 'patch-1',
  stage: 'storyboard',
  patch_type: 'storyboard_patch',
  target_type: 'storyboard_frame',
  target_id: 'shot-001',
  title: '强化前三秒钩子',
  reason: '原分镜冲突不够强。',
  before: { image_prompt: '原画面', video_prompt: '原镜头' },
  after: { image_prompt: '新画面', video_prompt: '新镜头' },
  status: 'proposed',
  priority: 'high',
  source_invocation_id: 'inv-1',
}]

describe('CreativePatchWorkbench', () => {
  it('shows patch diff and emits lifecycle actions', async () => {
    const wrapper = mount(CreativePatchWorkbench, {
      props: {
        patches,
        summary: { total: 1, blocking: 1, proposed: 1, edited: 0, approved: 0, applied: 0, rejected: 0 },
      },
    })

    expect(wrapper.text()).toContain('短视频导演台')
    expect(wrapper.text()).toContain('强化前三秒钩子')
    expect(wrapper.text()).toContain('原画面')
    expect(wrapper.text()).toContain('新画面')
    expect(wrapper.text()).toContain('待处理')

    await wrapper.find('button[data-action="approve"]').trigger('click')
    expect(wrapper.emitted('approve')[0][0].id).toBe('patch-1')

    await wrapper.find('button[data-action="apply"]').trigger('click')
    expect(wrapper.emitted('apply')[0][0].id).toBe('patch-1')
  })

  it('edits after fields and emits save', async () => {
    const wrapper = mount(CreativePatchWorkbench, {
      props: {
        patches,
        summary: { total: 1, blocking: 1 },
      },
    })

    const textarea = wrapper.find('textarea[data-field="image_prompt"]')
    await textarea.setValue('人工调整后的画面')
    await wrapper.find('button[data-action="save"]').trigger('click')

    expect(wrapper.emitted('save')[0][0]).toMatchObject({
      id: 'patch-1',
      after: { image_prompt: '人工调整后的画面', video_prompt: '新镜头' },
    })
  })
})
```

- [ ] **Step 2: Run component test and verify failure**

Run:

```powershell
cd web
npm exec vitest -- src/__tests__/creative-patch-workbench.test.js --run
```

Expected: fails because components do not exist.

- [ ] **Step 3: Implement summary strip**

`CreativePatchSummaryStrip.vue`:

```vue
<template>
  <section class="rounded-lg border border-cyan-400/20 bg-cyan-950/20 p-4" data-test="creative-patch-summary">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-base font-semibold text-cyan-50">创作补丁</h2>
        <p class="mt-1 text-sm text-cyan-100/80">专家改稿、分镜和提示词变更需要在生成前确认。</p>
      </div>
      <div class="grid grid-cols-3 gap-2 text-center text-xs text-cyan-50">
        <span class="rounded border border-white/10 px-3 py-2">全部 {{ summary.total || 0 }}</span>
        <span class="rounded border border-amber-300/30 px-3 py-2">待处理 {{ blockingCount }}</span>
        <span class="rounded border border-emerald-300/30 px-3 py-2">已应用 {{ summary.applied || 0 }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
})

const blockingCount = computed(() => props.summary.blocking || props.summary.proposed || 0)
</script>
```

- [ ] **Step 4: Implement workbench, list, diff, and actions**

Use props and events:

```javascript
const props = defineProps({
  patches: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['save', 'approve', 'reject', 'apply', 'open-invocation'])
```

`CreativePatchDiff.vue` must render one textarea for each string field in `after`:

```vue
<textarea
  v-if="typeof value === 'string'"
  :data-field="field"
  class="mt-1 min-h-20 w-full rounded border border-white/10 bg-zinc-950 p-2 text-sm text-zinc-100"
  :value="value"
  @input="updateField(field, $event.target.value)"
/>
```

`CreativePatchActions.vue` buttons must use these data attributes:

```vue
<button data-action="save" type="button" ...>保存修改</button>
<button data-action="approve" type="button" ...>批准</button>
<button data-action="apply" type="button" ...>应用</button>
<button data-action="reject" type="button" ...>拒绝</button>
```

- [ ] **Step 5: Run component tests**

Run:

```powershell
cd web
npm exec vitest -- src/__tests__/creative-patch-workbench.test.js --run
```

Expected: passes.

- [ ] **Step 6: Commit**

```powershell
git add web/src/components/agency/CreativePatchSummaryStrip.vue web/src/components/agency/CreativePatchWorkbench.vue web/src/components/agency/CreativePatchList.vue web/src/components/agency/CreativePatchDiff.vue web/src/components/agency/CreativePatchActions.vue web/src/__tests__/creative-patch-workbench.test.js
git commit -m "feat: add creative patch workbench components"
```

---

### Task 10: Agency Console Integration

**Files:**
- Modify: `web/src/views/AgencyConsolePage.vue`
- Modify: `web/src/__tests__/agency-console-page.test.js`

- [ ] **Step 1: Add failing console integration assertions**

Extend mocked `getAgencyConsole` payload with:

```javascript
creative_patch_summary: { total: 1, blocking: 1, proposed: 1, applied: 0 },
creative_patches: [{
  id: 'patch-1',
  stage: 'storyboard',
  patch_type: 'storyboard_patch',
  target_type: 'storyboard_frame',
  target_id: 'shot-001',
  title: '强化前三秒钩子',
  reason: '原分镜冲突不够强。',
  before: { image_prompt: '原画面' },
  after: { image_prompt: '新画面' },
  status: 'proposed',
  priority: 'high',
  source_invocation_id: 'inv-1',
}],
```

Add expectations:

```javascript
expect(wrapper.text()).toContain('短视频导演台')
expect(wrapper.text()).toContain('创作补丁')
expect(wrapper.text()).toContain('强化前三秒钩子')
```

- [ ] **Step 2: Run console test and verify failure**

Run:

```powershell
cd web
npm exec vitest -- src/__tests__/agency-console-page.test.js --run
```

Expected: fails because AgencyConsolePage does not render workbench components.

- [ ] **Step 3: Integrate workbench in `AgencyConsolePage.vue`**

Import:

```javascript
import {
  applyAgencyCreativePatch,
  approveAgencyCreativePatch,
  listAgencyCreativePatches,
  rejectAgencyCreativePatch,
  updateAgencyCreativePatch,
} from '../api/agency.js'
import CreativePatchSummaryStrip from '../components/agency/CreativePatchSummaryStrip.vue'
import CreativePatchWorkbench from '../components/agency/CreativePatchWorkbench.vue'
```

Add tabs:

```javascript
const activeTab = ref(route.query?.tab === 'experts' ? 'experts' : route.query?.tab === 'workbench' ? 'workbench' : 'control')
const creativePatchSummary = computed(() => consoleData.value?.creative_patch_summary || {})
const creativePatches = ref([])
```

After console load:

```javascript
creativePatches.value = data.creative_patches || []
```

Add workbench tab button:

```vue
<button type="button" data-tab="workbench" ... @click="activeTab = 'workbench'">短视频导演台</button>
```

Render:

```vue
<CreativePatchSummaryStrip
  v-if="activeTab === 'control' && creativePatchSummary.total"
  class="mb-5"
  :summary="creativePatchSummary"
/>

<CreativePatchWorkbench
  v-if="activeTab === 'workbench'"
  :summary="creativePatchSummary"
  :patches="creativePatches"
  @save="saveCreativePatch"
  @approve="approveCreativePatch"
  @reject="rejectCreativePatch"
  @apply="applyCreativePatch"
/>
```

Add handlers that call API and reload patch list:

```javascript
async function refreshCreativePatches() {
  const { data } = await listAgencyCreativePatches({ series_id: route.params.seriesId, run_id: consoleData.value?.latest_run?.id })
  creativePatches.value = data.items || []
  if (consoleData.value) consoleData.value.creative_patch_summary = data.summary || {}
}
```

- [ ] **Step 4: Run console tests**

Run:

```powershell
cd web
npm exec vitest -- src/__tests__/agency-console-page.test.js src/__tests__/creative-patch-workbench.test.js --run
```

Expected: passes.

- [ ] **Step 5: Commit**

```powershell
git add web/src/views/AgencyConsolePage.vue web/src/__tests__/agency-console-page.test.js
git commit -m "feat: integrate director workbench into agency console"
```

---

### Task 11: Full Verification

**Files:**
- No new source files unless a test reveals a direct defect in files modified above.

- [ ] **Step 1: Run backend targeted suite**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m pytest `
  tests/test_agency_creative_patch_contracts.py `
  tests/test_agency_creative_patch_service.py `
  tests/test_agency_creative_patch_api.py `
  tests/test_agency_multimodal_review.py `
  tests/test_agency_runtime.py `
  tests/test_agency_persistence.py `
  tests/test_agency_console.py `
  tests/test_video_production_creative_patch_gate.py `
  tests/test_video_production_linked_stage_execution.py `
  tests/test_video_production_final_gate.py `
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run backend compile check**

Run:

```powershell
cd server
.\.venv\Scripts\python.exe -m compileall app
```

Expected: exits 0.

- [ ] **Step 3: Run frontend targeted suite**

Run:

```powershell
cd web
npm exec vitest -- `
  src/__tests__/agency-api.test.js `
  src/__tests__/creative-patch-workbench.test.js `
  src/__tests__/agency-console-page.test.js `
  --run
```

Expected: all tests pass.

- [ ] **Step 4: Build frontend**

Run:

```powershell
cd web
npm run build
```

Expected: Vite build succeeds.

- [ ] **Step 5: Start dev servers for browser QA**

Backend:

```powershell
cd server
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd web
npm run dev -- --host 127.0.0.1 --port 5173
```

If either port is occupied, use the next free port and record it in the final report.

- [ ] **Step 6: Run gstack/browser QA**

Open:

```text
http://127.0.0.1:5173/series/<series-id>/agency-console?tab=workbench
```

Verify:

- Workbench tab renders.
- Patch summary strip renders.
- Patch list renders.
- Before/after diff renders.
- Approve/apply/reject buttons are visible and not overlapping.
- Browser console has no errors after interactions.
- Desktop and mobile screenshots have no incoherent text overlap.

- [ ] **Step 7: Save durable project memory if EverCore is running**

Run:

```powershell
.\tools\evercore-memory.ps1 health -BaseUrl "http://localhost:1995"
```

If healthy, save:

```powershell
.\tools\evercore-memory.ps1 save "Short-video creative workbench: added AgencyCreativePatch lifecycle, expert creative_patches, Pixelle preflight gate, director workbench UI, and multimodal review context. Key tests: agency creative patch service/API/runtime/persistence, video production creative patch gate, frontend workbench." -BaseUrl "http://localhost:1995" -GroupId "dy_auto"
```

Do not save API keys or provider secrets.

- [ ] **Step 8: Final commit**

If any verification fixes were needed:

```powershell
git add <changed-files>
git commit -m "fix: verify creative workbench flow"
```

## Self-Review

- Spec coverage: the plan covers expert creative patches, pre-generation approval, Pixelle preflight blocking, director workbench UI, and multimodal asset review.
- Type consistency: `AgencyCreativePatch`, `CreativePatchProposal`, `creative_patches`, `unresolved_patch_gate`, and frontend API names stay consistent across tasks.
- Scope check: Phase 1 and Phase 2 requirements from the design are both represented.
- Execution safety: every production mutation goes through a server-side apply function after approval.
- Test coverage: backend lifecycle, API, preflight gates, multimodal context, and frontend workbench interactions all have focused tests.
