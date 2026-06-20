# Dramatic Script Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a structured Dramatic Structure Matrix script generation pipeline for dy_auto with Pydantic V2 models, SQLAlchemy persistence, strict JSON prompts, expert gates, retry, and resume.

**Architecture:** Keep existing production services intact and add a focused script-generation layer. Reuse `PipelineRun.layers_json` for persistent state, `resolve_runtime_model_config()` for model selection, and `AgencyOrchestrator` for expert gates. Preserve old `from app.models import ...` imports by migrating `app.models` from a module to a package.

**Tech Stack:** Python 3, FastAPI service modules, Pydantic V2, SQLAlchemy ORM, Alembic, pytest, asyncio, OpenAI-compatible Bailian chat completions through existing runtime helpers.

---

## File Structure

- Modify: `server/app/models.py`
  - Move to `server/app/models/__init__.py` with content unchanged except for a script-model export import.
- Create: `server/app/models/script.py`
  - Pydantic V2 enums and models for beats, scenes, shots, stage wrappers, and final script.
- Modify: `server/app/db_models.py`
  - Add structured SQLAlchemy tables: `EpisodeScript`, `ScriptDramaticBeat`, `ScriptSceneOutline`, `ScriptVisualShot`.
- Create: `server/alembic/versions/0a1b2c3d4e5f_add_script_generation_tables.py`
  - Alembic migration for the new script tables.
- Create: `server/app/prompts/templates/script_stage1_dramatic_beats.md`
- Create: `server/app/prompts/templates/script_stage2_scene_outlines.md`
- Create: `server/app/prompts/templates/script_stage3_visual_shots.md`
  - Strict JSON Markdown prompt templates.
- Create: `server/app/services/script_pipeline.py`
  - `DynamicPromptBuilder`, `ScriptGenerationPipeline`, `PipelineManager`, `ScriptGenerationError`.
- Modify: `server/tests/conftest.py`
  - Import and clean the new SQLAlchemy models.
- Create: `server/tests/test_script_models.py`
- Create: `server/tests/test_script_prompt_builder.py`
- Create: `server/tests/test_script_pipeline.py`
- Create: `server/tests/test_models_package_imports.py`

---

### Task 1: Migrate `app.models` Into A Package Without Breaking Imports

**Files:**
- Modify: `server/app/models.py`
- Create: `server/app/models/__init__.py`
- Test: `server/tests/test_models_package_imports.py`

- [ ] **Step 1: Write the failing import compatibility test**

Create `server/tests/test_models_package_imports.py`:

```python
def test_legacy_app_models_imports_remain_available():
    from app.models import Task, TaskStatus, TaskType

    assert TaskType.NURTURE.value == "nurture"
    assert TaskStatus.PENDING.value == "pending"
    task = Task(type=TaskType.NURTURE, account_id="acc-001")
    assert task.status == TaskStatus.PENDING
```

- [ ] **Step 2: Run the compatibility test before migration**

Run:

```powershell
pytest server/tests/test_models_package_imports.py -q
```

Expected: PASS before the migration, proving the baseline import works.

- [ ] **Step 3: Move the module into a package**

Run:

```powershell
New-Item -ItemType Directory -Force -Path server/app/models
git mv server/app/models.py server/app/models/__init__.py
```

Do not edit the moved content in this step.

- [ ] **Step 4: Run the compatibility test after migration**

Run:

```powershell
pytest server/tests/test_models_package_imports.py server/tests/test_models.py server/tests/test_accounts_api.py -q
```

Expected: PASS. If imports fail, check that `server/app/models/__init__.py` exists and still contains the old `TaskType`, `TaskStatus`, and `Task` definitions.

- [ ] **Step 5: Commit the package migration**

Run:

```powershell
git add server/app/models/__init__.py server/tests/test_models_package_imports.py
git commit -m "refactor: migrate app models to package"
```

---

### Task 2: Add Pydantic V2 Script Domain Models

**Files:**
- Create: `server/app/models/script.py`
- Test: `server/tests/test_script_models.py`

- [ ] **Step 1: Write model validation tests**

Create `server/tests/test_script_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.script import (
    DramaticBeat,
    DramaticBeatList,
    DramaticBeatType,
    EpisodeScript,
    SceneOutline,
    SceneOutlineList,
    VisualShot,
    VisualShotList,
)


def _beats():
    return [
        DramaticBeat(beat_type=DramaticBeatType.HOOK, emotional_value="震惊", plot_summary="女主被当众羞辱，摔杯声压住全场。"),
        DramaticBeat(beat_type=DramaticBeatType.CONFLICT_1, emotional_value="憋屈", plot_summary="反派逼她签下不平等协议。"),
        DramaticBeat(beat_type=DramaticBeatType.REVERSAL, emotional_value="爽", plot_summary="女主亮出真实身份，局势倒转。"),
        DramaticBeat(beat_type=DramaticBeatType.CLIMAX, emotional_value="震撼", plot_summary="反派发现自己求错了人。"),
        DramaticBeat(beat_type=DramaticBeatType.CLIFFHANGER, emotional_value="紧张", plot_summary="真正幕后人推门出现。"),
    ]


def test_dramatic_beat_list_requires_five_core_beats():
    beat_list = DramaticBeatList(beats=_beats())

    assert [beat.beat_type for beat in beat_list.beats] == [
        DramaticBeatType.HOOK,
        DramaticBeatType.CONFLICT_1,
        DramaticBeatType.REVERSAL,
        DramaticBeatType.CLIMAX,
        DramaticBeatType.CLIFFHANGER,
    ]


def test_dramatic_beat_list_rejects_missing_core_beat():
    with pytest.raises(ValidationError, match="missing required dramatic beat"):
        DramaticBeatList(beats=_beats()[:-1])


def test_visual_shot_requires_positive_duration_and_emotional_narration():
    shot = VisualShot(
        shot_number=1,
        scene_number=1,
        beat_type=DramaticBeatType.HOOK,
        narration="震惊！你竟敢让我跪下？",
        visual_prompt="女主站在雨夜门口，破碎茶杯在脚边，强对比光。",
        video_prompt="镜头快速推近，女主抬眼，雨水划过脸颊。",
        duration=3.0,
    )

    assert shot.duration == 3.0


def test_visual_shot_rejects_narration_without_emotional_marker():
    with pytest.raises(ValidationError, match="emotional tone marker"):
        VisualShot(
            shot_number=1,
            scene_number=1,
            beat_type=DramaticBeatType.HOOK,
            narration="你让我跪下",
            visual_prompt="女主站在雨夜门口，破碎茶杯在脚边，强对比光。",
            video_prompt="镜头快速推近，女主抬眼，雨水划过脸颊。",
            duration=3.0,
        )


def test_episode_script_requires_structured_components():
    script = EpisodeScript(
        series_id="series-001",
        episode_id="episode-001",
        source_prompt="一句话短剧",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        dramatic_beats=DramaticBeatList(beats=_beats()),
        scene_outlines=SceneOutlineList(scenes=[
            SceneOutline(
                scene_number=1,
                dramatic_beat_type=DramaticBeatType.HOOK,
                location="雨夜豪门门口",
                characters=["女主", "反派"],
                conflict="反派逼女主下跪。",
                emotional_turn="从羞辱转为压迫。",
                visual_mandate="前3秒必须出现摔杯和身份反差。",
            )
        ]),
        visual_shots=VisualShotList(shots=[
            VisualShot(
                shot_number=1,
                scene_number=1,
                beat_type=DramaticBeatType.HOOK,
                narration="震惊！你竟敢让我跪下？",
                visual_prompt="女主站在雨夜门口，破碎茶杯在脚边，强对比光。",
                video_prompt="镜头快速推近，女主抬眼，雨水划过脸颊。",
                duration=3.0,
            )
        ]),
    )

    assert script.tags == ["都市逆袭"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest server/tests/test_script_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.script'`.

- [ ] **Step 3: Add `server/app/models/script.py`**

Create `server/app/models/script.py` with:

```python
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class DramaticBeatType(str, Enum):
    HOOK = "HOOK"
    CONFLICT_1 = "CONFLICT_1"
    REVERSAL = "REVERSAL"
    CLIMAX = "CLIMAX"
    CLIFFHANGER = "CLIFFHANGER"


class PipelineStage(str, Enum):
    DRAMATIC_BEATS = "dramatic_beats"
    SCENE_OUTLINES = "scene_outlines"
    VISUAL_SHOTS = "visual_shots"


REQUIRED_BEAT_SEQUENCE = [
    DramaticBeatType.HOOK,
    DramaticBeatType.CONFLICT_1,
    DramaticBeatType.REVERSAL,
    DramaticBeatType.CLIMAX,
    DramaticBeatType.CLIFFHANGER,
]

EMOTIONAL_TONE_MARKERS = {
    "爽", "憋屈", "震惊", "感动", "愤怒", "恐惧", "紧张", "崩溃", "委屈", "痛快", "震撼",
    "！", "?", "？",
}


class DramaticBeat(BaseModel):
    beat_type: DramaticBeatType
    emotional_value: str = Field(..., min_length=1, max_length=40)
    plot_summary: str = Field(..., min_length=1, max_length=500)


class DramaticBeatList(BaseModel):
    beats: list[DramaticBeat] = Field(..., min_length=5)

    @model_validator(mode="after")
    def require_core_beats(self):
        seen = [beat.beat_type for beat in self.beats]
        missing = [beat for beat in REQUIRED_BEAT_SEQUENCE if beat not in seen]
        if missing:
            missing_names = ", ".join(beat.value for beat in missing)
            raise ValueError(f"missing required dramatic beat: {missing_names}")
        return self


class SceneOutline(BaseModel):
    scene_number: int = Field(..., ge=1)
    dramatic_beat_type: DramaticBeatType
    location: str = Field(..., min_length=1, max_length=160)
    characters: list[str] = Field(default_factory=list)
    conflict: str = Field(..., min_length=1, max_length=500)
    emotional_turn: str = Field(..., min_length=1, max_length=240)
    visual_mandate: str = Field(..., min_length=1, max_length=500)


class SceneOutlineList(BaseModel):
    scenes: list[SceneOutline] = Field(..., min_length=1)


class VisualShot(BaseModel):
    shot_number: int = Field(..., ge=1)
    scene_number: int = Field(..., ge=1)
    beat_type: DramaticBeatType
    narration: str = Field(..., min_length=1, max_length=240)
    visual_prompt: str = Field(..., min_length=1, max_length=1200)
    video_prompt: str = Field(..., min_length=1, max_length=1200)
    duration: float = Field(..., gt=0)

    @field_validator("narration")
    @classmethod
    def narration_contains_emotional_marker(cls, value: str) -> str:
        if not any(marker in value for marker in EMOTIONAL_TONE_MARKERS):
            raise ValueError("narration must include an emotional tone marker")
        return value


class VisualShotList(BaseModel):
    shots: list[VisualShot] = Field(..., min_length=1)


class EpisodeScript(BaseModel):
    series_id: str
    episode_id: str
    source_prompt: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    target_duration_seconds: int = Field(..., ge=1)
    dramatic_beats: DramaticBeatList
    scene_outlines: SceneOutlineList
    visual_shots: VisualShotList
    agency_trace: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Export script models from `server/app/models/__init__.py`**

Append this block at the end of `server/app/models/__init__.py`:

```python
from app.models.script import (
    DramaticBeat,
    DramaticBeatList,
    DramaticBeatType,
    EpisodeScript,
    PipelineStage,
    SceneOutline,
    SceneOutlineList,
    VisualShot,
    VisualShotList,
)
```

- [ ] **Step 5: Run model tests**

Run:

```powershell
pytest server/tests/test_script_models.py server/tests/test_models_package_imports.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Pydantic models**

Run:

```powershell
git add server/app/models/__init__.py server/app/models/script.py server/tests/test_script_models.py
git commit -m "feat: add dramatic script pydantic models"
```

---

### Task 3: Add SQLAlchemy Script Persistence Models And Migration

**Files:**
- Modify: `server/app/db_models.py`
- Modify: `server/tests/conftest.py`
- Create: `server/alembic/versions/0a1b2c3d4e5f_add_script_generation_tables.py`
- Test: `server/tests/test_script_pipeline.py`

- [ ] **Step 1: Add persistence model tests**

Create the first part of `server/tests/test_script_pipeline.py`:

```python
from app.db_models import (
    Episode,
    EpisodeScript as DbEpisodeScript,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
    Series,
)


def test_script_sqlalchemy_tables_persist_structured_rows(db):
    series = Series(title="逆袭短剧", logline="她被羞辱后反转身份", genre="drama")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="第一集")
    db.add(episode)
    db.flush()

    script = DbEpisodeScript(
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags_json=["都市逆袭"],
        target_duration_seconds=60,
        status="completed",
    )
    db.add(script)
    db.flush()
    db.add(ScriptDramaticBeat(
        script_id=script.id,
        order_index=1,
        beat_type="HOOK",
        emotional_value="震惊",
        plot_summary="反派摔杯逼女主下跪。",
    ))
    db.add(ScriptSceneOutline(
        script_id=script.id,
        scene_number=1,
        dramatic_beat_type="HOOK",
        location="豪门门口",
        characters_json=["女主", "反派"],
        conflict="反派逼女主下跪。",
        emotional_turn="从羞辱到压迫。",
        visual_mandate="前3秒摔杯。",
    ))
    db.add(ScriptVisualShot(
        script_id=script.id,
        shot_number=1,
        scene_number=1,
        beat_type="HOOK",
        narration="震惊！你竟敢让我跪下？",
        visual_prompt="女主站在雨夜门口，破碎茶杯在脚边。",
        video_prompt="镜头快速推近，女主抬眼。",
        duration=3.0,
    ))
    db.commit()

    saved = db.query(DbEpisodeScript).filter_by(id=script.id).one()
    assert saved.tags_json == ["都市逆袭"]
    assert db.query(ScriptDramaticBeat).filter_by(script_id=script.id).count() == 1
    assert db.query(ScriptSceneOutline).filter_by(script_id=script.id).count() == 1
    assert db.query(ScriptVisualShot).filter_by(script_id=script.id).count() == 1
```

- [ ] **Step 2: Run the persistence test to verify it fails**

Run:

```powershell
pytest server/tests/test_script_pipeline.py::test_script_sqlalchemy_tables_persist_structured_rows -q
```

Expected: FAIL because `EpisodeScript` and child table models do not exist.

- [ ] **Step 3: Add SQLAlchemy models in `server/app/db_models.py`**

Insert these classes after the existing `PipelineRun` class:

```python
class EpisodeScript(Base):
    __tablename__ = "episode_scripts"
    __table_args__ = (
        Index("idx_episode_scripts_series_episode", "series_id", "episode_id"),
        Index("idx_episode_scripts_pipeline_run", "pipeline_run_id"),
        Index("idx_episode_scripts_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    series_id = Column(String(36), ForeignKey("series.id", ondelete="CASCADE"), nullable=False)
    episode_id = Column(String(36), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    source_prompt = Column(Text, nullable=False)
    tags_json = Column(JSON, nullable=True, default=list)
    target_duration_seconds = Column(Integer, nullable=False, default=60)
    status = Column(String(30), nullable=False, default="draft")
    agency_trace_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ScriptDramaticBeat(Base):
    __tablename__ = "script_dramatic_beats"
    __table_args__ = (
        UniqueConstraint("script_id", "order_index", name="uq_script_dramatic_beat_order"),
        Index("idx_script_dramatic_beats_script_id", "script_id"),
        Index("idx_script_dramatic_beats_type", "beat_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    beat_type = Column(String(40), nullable=False)
    emotional_value = Column(String(40), nullable=False)
    plot_summary = Column(Text, nullable=False)


class ScriptSceneOutline(Base):
    __tablename__ = "script_scene_outlines"
    __table_args__ = (
        UniqueConstraint("script_id", "scene_number", name="uq_script_scene_outline_number"),
        Index("idx_script_scene_outlines_script_id", "script_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    dramatic_beat_type = Column(String(40), nullable=False)
    location = Column(String(160), nullable=False)
    characters_json = Column(JSON, nullable=True, default=list)
    conflict = Column(Text, nullable=False)
    emotional_turn = Column(Text, nullable=False)
    visual_mandate = Column(Text, nullable=False)


class ScriptVisualShot(Base):
    __tablename__ = "script_visual_shots"
    __table_args__ = (
        UniqueConstraint("script_id", "shot_number", name="uq_script_visual_shot_number"),
        Index("idx_script_visual_shots_script_id", "script_id"),
        Index("idx_script_visual_shots_scene", "script_id", "scene_number"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    script_id = Column(String(36), ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    scene_number = Column(Integer, nullable=False)
    beat_type = Column(String(40), nullable=False)
    narration = Column(Text, nullable=False)
    visual_prompt = Column(Text, nullable=False)
    video_prompt = Column(Text, nullable=False)
    duration = Column(Float, nullable=False)
```

- [ ] **Step 4: Update `server/tests/conftest.py` imports and cleanup**

Add these models to the import list:

```python
EpisodeScript, ScriptDramaticBeat, ScriptSceneOutline, ScriptVisualShot,
```

Add cleanup entries before `PipelineRun` and `Episode`:

```python
ScriptVisualShot, ScriptSceneOutline, ScriptDramaticBeat, EpisodeScript,
```

- [ ] **Step 5: Add Alembic migration**

Create `server/alembic/versions/0a1b2c3d4e5f_add_script_generation_tables.py`:

```python
"""add script generation tables

Revision ID: 0a1b2c3d4e5f
Revises: 5e6f708192a3, f7a8b9c0d1e2
Create Date: 2026-06-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = ("5e6f708192a3", "f7a8b9c0d1e2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episode_scripts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("series_id", sa.String(length=36), sa.ForeignKey("series.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(length=36), sa.ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pipeline_run_id", sa.String(length=36), sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_prompt", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("target_duration_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("agency_trace_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_episode_scripts_series_episode", "episode_scripts", ["series_id", "episode_id"])
    op.create_index("idx_episode_scripts_pipeline_run", "episode_scripts", ["pipeline_run_id"])
    op.create_index("idx_episode_scripts_status", "episode_scripts", ["status"])

    op.create_table(
        "script_dramatic_beats",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("script_id", sa.String(length=36), sa.ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("beat_type", sa.String(length=40), nullable=False),
        sa.Column("emotional_value", sa.String(length=40), nullable=False),
        sa.Column("plot_summary", sa.Text(), nullable=False),
        sa.UniqueConstraint("script_id", "order_index", name="uq_script_dramatic_beat_order"),
    )
    op.create_index("idx_script_dramatic_beats_script_id", "script_dramatic_beats", ["script_id"])
    op.create_index("idx_script_dramatic_beats_type", "script_dramatic_beats", ["beat_type"])

    op.create_table(
        "script_scene_outlines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("script_id", sa.String(length=36), sa.ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("dramatic_beat_type", sa.String(length=40), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("characters_json", sa.JSON(), nullable=True),
        sa.Column("conflict", sa.Text(), nullable=False),
        sa.Column("emotional_turn", sa.Text(), nullable=False),
        sa.Column("visual_mandate", sa.Text(), nullable=False),
        sa.UniqueConstraint("script_id", "scene_number", name="uq_script_scene_outline_number"),
    )
    op.create_index("idx_script_scene_outlines_script_id", "script_scene_outlines", ["script_id"])

    op.create_table(
        "script_visual_shots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("script_id", sa.String(length=36), sa.ForeignKey("episode_scripts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_number", sa.Integer(), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("beat_type", sa.String(length=40), nullable=False),
        sa.Column("narration", sa.Text(), nullable=False),
        sa.Column("visual_prompt", sa.Text(), nullable=False),
        sa.Column("video_prompt", sa.Text(), nullable=False),
        sa.Column("duration", sa.Float(), nullable=False),
        sa.UniqueConstraint("script_id", "shot_number", name="uq_script_visual_shot_number"),
    )
    op.create_index("idx_script_visual_shots_script_id", "script_visual_shots", ["script_id"])
    op.create_index("idx_script_visual_shots_scene", "script_visual_shots", ["script_id", "scene_number"])


def downgrade() -> None:
    op.drop_index("idx_script_visual_shots_scene", table_name="script_visual_shots")
    op.drop_index("idx_script_visual_shots_script_id", table_name="script_visual_shots")
    op.drop_table("script_visual_shots")
    op.drop_index("idx_script_scene_outlines_script_id", table_name="script_scene_outlines")
    op.drop_table("script_scene_outlines")
    op.drop_index("idx_script_dramatic_beats_type", table_name="script_dramatic_beats")
    op.drop_index("idx_script_dramatic_beats_script_id", table_name="script_dramatic_beats")
    op.drop_table("script_dramatic_beats")
    op.drop_index("idx_episode_scripts_status", table_name="episode_scripts")
    op.drop_index("idx_episode_scripts_pipeline_run", table_name="episode_scripts")
    op.drop_index("idx_episode_scripts_series_episode", table_name="episode_scripts")
    op.drop_table("episode_scripts")
```

- [ ] **Step 6: Run persistence test**

Run:

```powershell
pytest server/tests/test_script_pipeline.py::test_script_sqlalchemy_tables_persist_structured_rows -q
```

Expected: PASS.

- [ ] **Step 7: Commit persistence models**

Run:

```powershell
git add server/app/db_models.py server/alembic/versions/0a1b2c3d4e5f_add_script_generation_tables.py server/tests/conftest.py server/tests/test_script_pipeline.py
git commit -m "feat: add structured script persistence"
```

---

### Task 4: Add Strict JSON Prompt Templates And Dynamic Prompt Builder

**Files:**
- Create: `server/app/prompts/templates/script_stage1_dramatic_beats.md`
- Create: `server/app/prompts/templates/script_stage2_scene_outlines.md`
- Create: `server/app/prompts/templates/script_stage3_visual_shots.md`
- Create: `server/app/services/script_pipeline.py`
- Test: `server/tests/test_script_prompt_builder.py`

- [ ] **Step 1: Write prompt builder tests**

Create `server/tests/test_script_prompt_builder.py`:

```python
from app.models.script import DramaticBeatType, PipelineStage
from app.services.script_pipeline import DynamicPromptBuilder


def test_prompt_builder_injects_hook_and_tag_constraints():
    builder = DynamicPromptBuilder()

    payload = builder.build(
        stage=PipelineStage.DRAMATIC_BEATS,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭", "歪嘴战神"],
        target_duration_seconds=60,
        beat_types=[DramaticBeatType.HOOK],
    )

    assert "只输出严格 JSON" in payload.system_prompt
    assert "前3秒必须出现视觉冲突" in payload.user_prompt
    assert "台词字数不得超过15字" in payload.user_prompt
    assert "现代层级压力" in payload.user_prompt
    assert "被压制的主角身份" in payload.user_prompt


def test_prompt_builder_injects_climax_constraints():
    builder = DynamicPromptBuilder()

    payload = builder.build(
        stage=PipelineStage.VISUAL_SHOTS,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["主母黑化"],
        target_duration_seconds=60,
        beat_types=[DramaticBeatType.CLIMAX],
        previous_outputs={"scene_outlines": {"scenes": []}},
    )

    assert "必须完成身份反转" in payload.user_prompt
    assert "低角度仰拍" in payload.user_prompt
    assert "背叛" in payload.user_prompt
    assert "不得输出 Markdown" in payload.system_prompt
```

- [ ] **Step 2: Run prompt tests to verify they fail**

Run:

```powershell
pytest server/tests/test_script_prompt_builder.py -q
```

Expected: FAIL because `app.services.script_pipeline` does not exist.

- [ ] **Step 3: Create Markdown prompt templates**

Create `server/app/prompts/templates/script_stage1_dramatic_beats.md`:

```markdown
## SYSTEM
你是 dy_auto 的短剧戏剧结构生成器。只输出严格 JSON。不得输出 Markdown。不得输出解释、分析、寒暄或代码块。

## USER
根据输入生成 DramaticBeatList。

输入:
{{source_prompt}}

标签:
{{tags}}

目标时长:
{{target_duration_seconds}} 秒

强制约束:
{{constraints}}

只允许输出:
{
  "beats": [
    {"beat_type": "HOOK", "emotional_value": "震惊", "plot_summary": "..."},
    {"beat_type": "CONFLICT_1", "emotional_value": "憋屈", "plot_summary": "..."},
    {"beat_type": "REVERSAL", "emotional_value": "爽", "plot_summary": "..."},
    {"beat_type": "CLIMAX", "emotional_value": "震撼", "plot_summary": "..."},
    {"beat_type": "CLIFFHANGER", "emotional_value": "紧张", "plot_summary": "..."}
  ]
}
```

Create `server/app/prompts/templates/script_stage2_scene_outlines.md`:

```markdown
## SYSTEM
你是 dy_auto 的短剧逐场景大纲生成器。只输出严格 JSON。不得输出 Markdown。不得输出解释、分析、寒暄或代码块。

## USER
根据已通过专家审核的 DramaticBeatList 生成 SceneOutlineList。

输入:
{{source_prompt}}

标签:
{{tags}}

目标时长:
{{target_duration_seconds}} 秒

上一阶段输出:
{{previous_outputs}}

强制约束:
{{constraints}}

只允许输出:
{
  "scenes": [
    {
      "scene_number": 1,
      "dramatic_beat_type": "HOOK",
      "location": "...",
      "characters": ["..."],
      "conflict": "...",
      "emotional_turn": "...",
      "visual_mandate": "..."
    }
  ]
}
```

Create `server/app/prompts/templates/script_stage3_visual_shots.md`:

```markdown
## SYSTEM
你是 dy_auto 的短剧分镜与提示词生成器。只输出严格 JSON。不得输出 Markdown。不得输出解释、分析、寒暄或代码块。

## USER
根据已通过专家审核的 DramaticBeatList 与 SceneOutlineList 生成 VisualShotList。

输入:
{{source_prompt}}

标签:
{{tags}}

目标时长:
{{target_duration_seconds}} 秒

上一阶段输出:
{{previous_outputs}}

强制约束:
{{constraints}}

只允许输出:
{
  "shots": [
    {
      "shot_number": 1,
      "scene_number": 1,
      "beat_type": "HOOK",
      "narration": "震惊！...",
      "visual_prompt": "...",
      "video_prompt": "...",
      "duration": 3.0
    }
  ]
}
```

- [ ] **Step 4: Add prompt builder skeleton in `server/app/services/script_pipeline.py`**

Create `server/app/services/script_pipeline.py` with this initial content:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models.script import DramaticBeatType, PipelineStage


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "prompts" / "templates"


@dataclass(frozen=True)
class PromptPayload:
    system_prompt: str
    user_prompt: str


BEAT_CONSTRAINTS = {
    DramaticBeatType.HOOK: [
        "前3秒必须出现视觉冲突（如摔杯子、下跪、耳光或身份反差）",
        "台词字数不得超过15字",
        "语气必须极端",
    ],
    DramaticBeatType.CLIMAX: [
        "必须完成身份反转",
        "反派角色产生震惊、恐惧的视觉表现",
        "主角机位采用低角度仰拍以增强压迫感",
    ],
}

TAG_CONSTRAINTS = {
    "歪嘴战神": ["被压制的主角身份", "旁人公开轻蔑", "精准亮明权力或武力反差"],
    "都市逆袭": ["现代层级压力", "公开 stakes", "金钱或身份反差", "当场反转"],
    "主母黑化": ["家庭权力秩序", "背叛", "情绪冷转", "克制反击"],
}

TEMPLATE_NAMES = {
    PipelineStage.DRAMATIC_BEATS: "script_stage1_dramatic_beats.md",
    PipelineStage.SCENE_OUTLINES: "script_stage2_scene_outlines.md",
    PipelineStage.VISUAL_SHOTS: "script_stage3_visual_shots.md",
}


class DynamicPromptBuilder:
    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self.template_dir = template_dir

    def build(
        self,
        *,
        stage: PipelineStage,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        beat_types: list[DramaticBeatType] | None = None,
        previous_outputs: dict[str, Any] | None = None,
    ) -> PromptPayload:
        template = self._read_template(stage)
        system_prompt, user_prompt = self._split_template(template)
        rendered_user = self._render(
            user_prompt,
            source_prompt=source_prompt,
            tags="、".join(tags) if tags else "无",
            target_duration_seconds=str(target_duration_seconds),
            previous_outputs=json.dumps(previous_outputs or {}, ensure_ascii=False, sort_keys=True),
            constraints="\n".join(self._constraints(tags, beat_types or [])),
        )
        return PromptPayload(system_prompt=system_prompt.strip(), user_prompt=rendered_user.strip())

    def _read_template(self, stage: PipelineStage) -> str:
        return (self.template_dir / TEMPLATE_NAMES[stage]).read_text(encoding="utf-8")

    def _split_template(self, template: str) -> tuple[str, str]:
        system_marker = "## SYSTEM"
        user_marker = "## USER"
        if system_marker not in template or user_marker not in template:
            raise ValueError("script prompt template must contain ## SYSTEM and ## USER sections")
        system_part, user_part = template.split(user_marker, 1)
        return system_part.replace(system_marker, "", 1), user_part

    def _render(self, template: str, **values: str) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        return rendered

    def _constraints(self, tags: list[str], beat_types: list[DramaticBeatType]) -> list[str]:
        constraints: list[str] = []
        for beat_type in beat_types:
            constraints.extend(BEAT_CONSTRAINTS.get(beat_type, []))
        for tag in tags:
            constraints.extend(TAG_CONSTRAINTS.get(tag, [f"保留标签语境: {tag}"]))
        return constraints
```

- [ ] **Step 5: Run prompt tests**

Run:

```powershell
pytest server/tests/test_script_prompt_builder.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit prompt builder and templates**

Run:

```powershell
git add server/app/prompts/templates server/app/services/script_pipeline.py server/tests/test_script_prompt_builder.py
git commit -m "feat: add script prompt builder"
```

---

### Task 5: Implement Async Script Generation Pipeline With Gates And Retry

**Files:**
- Modify: `server/app/services/script_pipeline.py`
- Test: `server/tests/test_script_pipeline.py`

- [ ] **Step 1: Add pipeline behavior tests**

Append to `server/tests/test_script_pipeline.py`:

```python
import pytest

from app.db_models import Episode, PipelineRun, Series
from app.models.script import DramaticBeatType, EpisodeScript
from app.services.script_pipeline import PipelineManager, ScriptGenerationError, ScriptGenerationPipeline


class FakeModelClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, *, system_prompt, user_prompt, runtime_config):
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "runtime_config": runtime_config,
        })
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeGate:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    async def __call__(self, db, *, gate_name, series_id, episode_id, pipeline_run_id, stage_context, runtime_config):
        self.calls.append({
            "gate_name": gate_name,
            "series_id": series_id,
            "episode_id": episode_id,
            "pipeline_run_id": pipeline_run_id,
            "stage_context": stage_context,
            "runtime_config": runtime_config,
        })
        status = self.statuses.pop(0)
        return {"stage": gate_name, "stage_status": status, "invocation_ids": [f"{gate_name}-1"], "invocations": []}


def _series_episode(db):
    series = Series(title="逆袭短剧", logline="她被羞辱后反转身份", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, title="第一集")
    db.add(episode)
    db.flush()
    return series, episode


def _stage_outputs():
    beats = {
        "beats": [
            {"beat_type": "HOOK", "emotional_value": "震惊", "plot_summary": "反派摔杯逼女主下跪。"},
            {"beat_type": "CONFLICT_1", "emotional_value": "憋屈", "plot_summary": "反派逼她签协议。"},
            {"beat_type": "REVERSAL", "emotional_value": "爽", "plot_summary": "女主亮明身份。"},
            {"beat_type": "CLIMAX", "emotional_value": "震撼", "plot_summary": "反派发现自己求错人。"},
            {"beat_type": "CLIFFHANGER", "emotional_value": "紧张", "plot_summary": "幕后人出现。"},
        ]
    }
    scenes = {
        "scenes": [
            {
                "scene_number": 1,
                "dramatic_beat_type": "HOOK",
                "location": "豪门门口",
                "characters": ["女主", "反派"],
                "conflict": "反派逼女主下跪。",
                "emotional_turn": "羞辱压到极点。",
                "visual_mandate": "前3秒摔杯。",
            }
        ]
    }
    shots = {
        "shots": [
            {
                "shot_number": 1,
                "scene_number": 1,
                "beat_type": "HOOK",
                "narration": "震惊！你竟敢让我跪下？",
                "visual_prompt": "女主站在雨夜门口，破碎茶杯在脚边。",
                "video_prompt": "镜头快速推近，女主抬眼。",
                "duration": 3.0,
            }
        ]
    }
    return beats, scenes, shots


@pytest.mark.asyncio
async def test_script_pipeline_runs_three_stages_sequentially(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["completed", "completed"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    result = await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
    )

    assert isinstance(result, EpisodeScript)
    assert [beat.beat_type for beat in result.dramatic_beats.beats][0] == DramaticBeatType.HOOK
    assert len(pipeline.model_client.calls) == 3
    assert [call["gate_name"] for call in pipeline.gate_runner.calls] == ["dramatic_beats", "scene_outlines"]
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    state = saved_run.layers_json["script_generation"]
    assert state["stages"]["visual_shots"]["status"] == "completed"


@pytest.mark.asyncio
async def test_script_pipeline_blocks_stage_two_when_gate_one_blocks(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["blocked"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    with pytest.raises(ScriptGenerationError, match="expert gate blocked"):
        await manager.start_or_resume(
            db,
            series_id=series.id,
            episode_id=episode.id,
            source_prompt="她被逼下跪，却亮出集团继承人身份",
            tags=["都市逆袭"],
            target_duration_seconds=60,
        )

    assert len(pipeline.model_client.calls) == 1
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    assert saved_run.layers_json["script_generation"]["human_intervention_required"] is True


@pytest.mark.asyncio
async def test_script_pipeline_retries_stage_twice_then_marks_human_intervention(db):
    series, episode = _series_episode(db)
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([
            RuntimeError("bad json"),
            RuntimeError("bad json"),
            RuntimeError("bad json"),
        ]),
        gate_runner=FakeGate([]),
    )
    manager = PipelineManager(pipeline=pipeline)

    with pytest.raises(ScriptGenerationError) as exc:
        await manager.start_or_resume(
            db,
            series_id=series.id,
            episode_id=episode.id,
            source_prompt="她被逼下跪，却亮出集团继承人身份",
            tags=["都市逆袭"],
            target_duration_seconds=60,
        )

    assert exc.value.attempts == 3
    saved_run = db.query(PipelineRun).filter_by(series_id=series.id, episode_id=episode.id).one()
    stage = saved_run.layers_json["script_generation"]["stages"]["dramatic_beats"]
    assert stage["attempts"] == 3
    assert stage["status"] == "failed"
    assert saved_run.layers_json["script_generation"]["human_intervention_required"] is True


@pytest.mark.asyncio
async def test_script_pipeline_resume_skips_completed_stage(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    manager = PipelineManager(pipeline=ScriptGenerationPipeline(
        model_client=FakeModelClient([beats]),
        gate_runner=FakeGate(["completed"]),
    ))
    run = manager.get_or_create_run(db, series_id=series.id, episode_id=episode.id)
    manager.mark_stage_completed_for_test(
        db,
        run=run,
        stage_name="dramatic_beats",
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
        output=beats,
        gate_trace={"stage_status": "completed"},
    )
    pipeline = ScriptGenerationPipeline(
        model_client=FakeModelClient([scenes, shots]),
        gate_runner=FakeGate(["completed"]),
    )
    manager = PipelineManager(pipeline=pipeline)

    result = await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
    )

    assert result.dramatic_beats.beats[0].beat_type == DramaticBeatType.HOOK
    assert len(pipeline.model_client.calls) == 2
```

- [ ] **Step 2: Run pipeline tests to verify they fail**

Run:

```powershell
pytest server/tests/test_script_pipeline.py -q
```

Expected: FAIL because `ScriptGenerationPipeline` and `PipelineManager` are not implemented.

- [ ] **Step 3: Implement `ScriptGenerationError` and JSON parsing**

Add to `server/app/services/script_pipeline.py`:

```python
class ScriptGenerationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        pipeline_run_id: str,
        attempts: int,
        error_code: str,
        human_intervention_required: bool = True,
    ):
        super().__init__(message)
        self.stage = stage
        self.pipeline_run_id = pipeline_run_id
        self.attempts = attempts
        self.error_code = error_code
        self.human_intervention_required = human_intervention_required


def _load_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("script model response must be a JSON object or JSON string")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("script model response must be a JSON object")
    return parsed
```

- [ ] **Step 4: Implement default model client and gate runner**

Add:

```python
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db_models import Episode, PipelineRun
from app.models.script import DramaticBeatList, EpisodeScript, SceneOutlineList, VisualShotList
from app.services.agency_orchestrator import AgencyOrchestrator
from app.services.agency_runtime import _default_model_client
from app.services.runtime_model_config import RuntimeModelConfigError, resolve_runtime_model_config


async def default_script_model_client(*, system_prompt: str, user_prompt: str, runtime_config: dict[str, Any]) -> Any:
    response = await _default_model_client(system_prompt, user_prompt, runtime_config)
    return response["content"]


async def default_gate_runner(
    db: Session,
    *,
    gate_name: str,
    series_id: str,
    episode_id: str,
    pipeline_run_id: str,
    stage_context: dict[str, Any],
    runtime_config: dict[str, Any],
) -> dict[str, Any]:
    orchestrator = AgencyOrchestrator()
    if gate_name == "dramatic_beats":
        return await orchestrator.run_storyboard_review(
            db,
            series_id=series_id,
            episode_id=episode_id,
            pipeline_run_id=pipeline_run_id,
            stage_context=stage_context,
            runtime_config=runtime_config,
        )
    return await orchestrator.run_style_lock_review(
        db,
        series_id=series_id,
        episode_id=episode_id,
        pipeline_run_id=pipeline_run_id,
        stage_context=stage_context,
        runtime_config=runtime_config,
    )
```

- [ ] **Step 5: Implement state helpers**

Add helper functions:

```python
import hashlib


SCRIPT_STATE_KEY = "script_generation"
MAX_STAGE_RETRIES = 2


def _input_hash(*, stage: PipelineStage, source_prompt: str, tags: list[str], target_duration_seconds: int, previous_outputs: dict[str, Any]) -> str:
    payload = {
        "stage": stage.value,
        "source_prompt": source_prompt,
        "tags": tags,
        "target_duration_seconds": target_duration_seconds,
        "previous_outputs": previous_outputs,
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _script_state(run: PipelineRun) -> dict[str, Any]:
    layers = dict(run.layers_json or {})
    state = dict(layers.get(SCRIPT_STATE_KEY) or {})
    state.setdefault("current_stage", PipelineStage.DRAMATIC_BEATS.value)
    state.setdefault("human_intervention_required", False)
    state.setdefault("stages", {})
    layers[SCRIPT_STATE_KEY] = state
    run.layers_json = layers
    return state


def _persist_run_state(db: Session, run: PipelineRun) -> None:
    flag_modified(run, "layers_json")
    db.add(run)
    db.commit()
    db.refresh(run)
```

- [ ] **Step 6: Implement `ScriptGenerationPipeline`**

Add:

```python
class ScriptGenerationPipeline:
    def __init__(self, *, model_client=default_script_model_client, gate_runner=default_gate_runner, prompt_builder: DynamicPromptBuilder | None = None):
        self.model_client = model_client
        self.gate_runner = gate_runner
        self.prompt_builder = prompt_builder or DynamicPromptBuilder()

    async def generate_stage(
        self,
        *,
        stage: PipelineStage,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        previous_outputs: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> DramaticBeatList | SceneOutlineList | VisualShotList:
        beat_types = self._beat_types(stage, previous_outputs)
        payload = self.prompt_builder.build(
            stage=stage,
            source_prompt=source_prompt,
            tags=tags,
            target_duration_seconds=target_duration_seconds,
            beat_types=beat_types,
            previous_outputs=previous_outputs,
        )
        raw = await self.model_client(
            system_prompt=payload.system_prompt,
            user_prompt=payload.user_prompt,
            runtime_config=runtime_config,
        )
        data = _load_json_object(raw)
        if stage == PipelineStage.DRAMATIC_BEATS:
            return DramaticBeatList.model_validate(data)
        if stage == PipelineStage.SCENE_OUTLINES:
            return SceneOutlineList.model_validate(data)
        return VisualShotList.model_validate(data)

    def _beat_types(self, stage: PipelineStage, previous_outputs: dict[str, Any]) -> list[DramaticBeatType]:
        if stage == PipelineStage.DRAMATIC_BEATS:
            return [DramaticBeatType.HOOK, DramaticBeatType.CLIMAX]
        beats = (previous_outputs.get("dramatic_beats") or {}).get("beats") or []
        result = []
        for beat in beats:
            try:
                result.append(DramaticBeatType(beat["beat_type"]))
            except (KeyError, ValueError, TypeError):
                continue
        return result
```

- [ ] **Step 7: Implement `PipelineManager`**

Add:

```python
class PipelineManager:
    def __init__(self, *, pipeline: ScriptGenerationPipeline | None = None):
        self.pipeline = pipeline or ScriptGenerationPipeline()

    def get_or_create_run(self, db: Session, *, series_id: str, episode_id: str) -> PipelineRun:
        run = (
            db.query(PipelineRun)
            .filter(PipelineRun.series_id == series_id, PipelineRun.episode_id == episode_id, PipelineRun.mode == "script_generation")
            .order_by(PipelineRun.created_at.desc())
            .first()
        )
        if run:
            return run
        run = PipelineRun(series_id=series_id, episode_id=episode_id, mode="script_generation", status="running", current_layer=1)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    async def start_or_resume(
        self,
        db: Session,
        *,
        series_id: str,
        episode_id: str,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        explicit_model_id: str | None = None,
    ) -> EpisodeScript:
        run = self.get_or_create_run(db, series_id=series_id, episode_id=episode_id)
        runtime_config = resolve_runtime_model_config(db, "script_generation", explicit_model_id)
        gate_runtime_config = resolve_runtime_model_config(db, "llm_agency_expert_review")
        previous: dict[str, Any] = {}
        beats = await self._run_stage(db, run, PipelineStage.DRAMATIC_BEATS, source_prompt, tags, target_duration_seconds, previous, runtime_config)
        previous["dramatic_beats"] = beats.model_dump(mode="json")
        await self._run_gate(db, run, "dramatic_beats", series_id, episode_id, previous, gate_runtime_config)
        scenes = await self._run_stage(db, run, PipelineStage.SCENE_OUTLINES, source_prompt, tags, target_duration_seconds, previous, runtime_config)
        previous["scene_outlines"] = scenes.model_dump(mode="json")
        await self._run_gate(db, run, "scene_outlines", series_id, episode_id, previous, gate_runtime_config)
        shots = await self._run_stage(db, run, PipelineStage.VISUAL_SHOTS, source_prompt, tags, target_duration_seconds, previous, runtime_config)
        previous["visual_shots"] = shots.model_dump(mode="json")
        result = EpisodeScript(
            series_id=series_id,
            episode_id=episode_id,
            source_prompt=source_prompt,
            tags=tags,
            target_duration_seconds=target_duration_seconds,
            dramatic_beats=beats,
            scene_outlines=scenes,
            visual_shots=shots,
            agency_trace=self._agency_trace(run),
        )
        self._write_snapshots(db, run, result)
        return result
```

Complete the class with `_run_stage`, `_run_gate`, `_stage_record`, `_fail_stage`, `_write_snapshots`, `_agency_trace`, and `mark_stage_completed_for_test`. Each method must persist `PipelineRun.layers_json` before returning or raising.

- [ ] **Step 8: Run pipeline tests**

Run:

```powershell
pytest server/tests/test_script_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit pipeline controller**

Run:

```powershell
git add server/app/services/script_pipeline.py server/tests/test_script_pipeline.py
git commit -m "feat: add dramatic script pipeline"
```

---

### Task 6: Persist Structured Script Rows And Compatibility Snapshots

**Files:**
- Modify: `server/app/services/script_pipeline.py`
- Test: `server/tests/test_script_pipeline.py`

- [ ] **Step 1: Add writeback tests**

Append:

```python
from app.db_models import EpisodeScript as DbEpisodeScript, ScriptDramaticBeat, ScriptSceneOutline, ScriptVisualShot


@pytest.mark.asyncio
async def test_script_pipeline_persists_structured_script_and_snapshots(db):
    series, episode = _series_episode(db)
    beats, scenes, shots = _stage_outputs()
    manager = PipelineManager(pipeline=ScriptGenerationPipeline(
        model_client=FakeModelClient([beats, scenes, shots]),
        gate_runner=FakeGate(["completed", "completed"]),
    ))

    await manager.start_or_resume(
        db,
        series_id=series.id,
        episode_id=episode.id,
        source_prompt="她被逼下跪，却亮出集团继承人身份",
        tags=["都市逆袭"],
        target_duration_seconds=60,
    )

    saved_script = db.query(DbEpisodeScript).filter_by(episode_id=episode.id).one()
    assert saved_script.status == "completed"
    assert db.query(ScriptDramaticBeat).filter_by(script_id=saved_script.id).count() == 5
    assert db.query(ScriptSceneOutline).filter_by(script_id=saved_script.id).count() == 1
    assert db.query(ScriptVisualShot).filter_by(script_id=saved_script.id).count() == 1
    db.refresh(episode)
    assert episode.script_json["source"] == "dramatic_script_pipeline"
    assert episode.storyboard_json["frames"][0]["image_prompt"] == "女主站在雨夜门口，破碎茶杯在脚边。"
```

- [ ] **Step 2: Run writeback test to verify it fails**

Run:

```powershell
pytest server/tests/test_script_pipeline.py::test_script_pipeline_persists_structured_script_and_snapshots -q
```

Expected: FAIL until `_write_snapshots` persists tables and snapshots.

- [ ] **Step 3: Implement structured writeback**

In `PipelineManager._write_snapshots`, use this behavior:

```python
from app.db_models import (
    EpisodeScript as DbEpisodeScript,
    ScriptDramaticBeat,
    ScriptSceneOutline,
    ScriptVisualShot,
)


def _write_snapshots(self, db: Session, run: PipelineRun, script: EpisodeScript) -> None:
    db_script = DbEpisodeScript(
        series_id=script.series_id,
        episode_id=script.episode_id,
        pipeline_run_id=run.id,
        source_prompt=script.source_prompt,
        tags_json=list(script.tags),
        target_duration_seconds=script.target_duration_seconds,
        status="completed",
        agency_trace_json=script.agency_trace,
    )
    db.add(db_script)
    db.flush()
    for index, beat in enumerate(script.dramatic_beats.beats, start=1):
        db.add(ScriptDramaticBeat(
            script_id=db_script.id,
            order_index=index,
            beat_type=beat.beat_type.value,
            emotional_value=beat.emotional_value,
            plot_summary=beat.plot_summary,
        ))
    for scene in script.scene_outlines.scenes:
        db.add(ScriptSceneOutline(
            script_id=db_script.id,
            scene_number=scene.scene_number,
            dramatic_beat_type=scene.dramatic_beat_type.value,
            location=scene.location,
            characters_json=list(scene.characters),
            conflict=scene.conflict,
            emotional_turn=scene.emotional_turn,
            visual_mandate=scene.visual_mandate,
        ))
    for shot in script.visual_shots.shots:
        db.add(ScriptVisualShot(
            script_id=db_script.id,
            shot_number=shot.shot_number,
            scene_number=shot.scene_number,
            beat_type=shot.beat_type.value,
            narration=shot.narration,
            visual_prompt=shot.visual_prompt,
            video_prompt=shot.video_prompt,
            duration=shot.duration,
        ))
    episode = db.query(Episode).filter(Episode.id == script.episode_id).one()
    episode.script_json = self._script_snapshot(script, db_script.id)
    episode.storyboard_json = self._storyboard_snapshot(script)
    flag_modified(episode, "script_json")
    flag_modified(episode, "storyboard_json")
    run.status = "completed"
    run.layers_json[SCRIPT_STATE_KEY]["current_stage"] = PipelineStage.VISUAL_SHOTS.value
    flag_modified(run, "layers_json")
    db.commit()
```

- [ ] **Step 4: Implement snapshot helpers**

Add:

```python
def _script_snapshot(self, script: EpisodeScript, db_script_id: str) -> dict[str, Any]:
    return {
        "source": "dramatic_script_pipeline",
        "script_id": db_script_id,
        "source_prompt": script.source_prompt,
        "tags": script.tags,
        "target_duration_seconds": script.target_duration_seconds,
        "dramatic_beats": script.dramatic_beats.model_dump(mode="json"),
        "scene_outlines": script.scene_outlines.model_dump(mode="json"),
        "visual_shots": script.visual_shots.model_dump(mode="json"),
        "agency_trace": script.agency_trace,
    }


def _storyboard_snapshot(self, script: EpisodeScript) -> dict[str, Any]:
    frames = []
    for shot in script.visual_shots.shots:
        frames.append({
            "frame_id": f"shot-{shot.shot_number:03d}",
            "image_prompt": shot.visual_prompt,
            "video_prompt": shot.video_prompt,
            "narration": shot.narration,
            "duration": shot.duration,
            "action": shot.beat_type.value,
            "emotion": shot.beat_type.value,
            "shot_type": "dramatic_script_pipeline",
        })
    return {
        "source": "dramatic_script_pipeline",
        "frames": frames,
        "frame_count": len(frames),
        "total_duration": sum(frame["duration"] for frame in frames),
    }
```

- [ ] **Step 5: Run writeback tests**

Run:

```powershell
pytest server/tests/test_script_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit writeback**

Run:

```powershell
git add server/app/services/script_pipeline.py server/tests/test_script_pipeline.py
git commit -m "feat: persist dramatic script outputs"
```

---

### Task 7: Final Verification And Regression Checks

**Files:**
- Read: all files touched by Tasks 1-6.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
pytest server/tests/test_script_models.py server/tests/test_script_prompt_builder.py server/tests/test_script_pipeline.py server/tests/test_models_package_imports.py -q
```

Expected: PASS.

- [ ] **Step 2: Run compatibility tests**

Run:

```powershell
pytest server/tests/test_models.py server/tests/test_accounts_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Search for broken imports and accidental text script storage**

Run:

```powershell
rg -n "from app\\.models import|import app\\.models|script_text|raw_script|full_script" server/app server/tests
```

Expected:

- Import results can exist and should still point at `app.models`.
- No new `script_text`, `raw_script`, or `full_script` storage field should appear in script-generation code.

- [ ] **Step 4: Check git diff scope**

Run:

```powershell
git status --short
git diff --stat HEAD
```

Expected:

- Only planned files from this plan are modified by this implementation.
- Existing unrelated working-tree changes remain untouched.

- [ ] **Step 5: Save concise EverCore memory if service is available**

Run:

```powershell
.\tools\evercore-memory.ps1 health -BaseUrl "http://localhost:1995"
```

If health succeeds, save:

```powershell
.\tools\evercore-memory.ps1 save "Implemented dramatic script pipeline: app.models package migration, Pydantic script models, structured SQLAlchemy tables, strict JSON templates, async pipeline with retries/resume/expert gates, and focused tests." -BaseUrl "http://localhost:1995" -GroupId "dy_auto"
```

If health fails, record in the final response that EverCore was unavailable.

- [ ] **Step 6: Final commit if any verification-only fixes were needed**

Run only if Step 1 or Step 2 required a small fix:

```powershell
git add <fixed-files>
git commit -m "test: stabilize dramatic script pipeline"
```

---

## Self-Review

Spec coverage:

- `models/script.py` Pydantic V2 models: Task 2.
- Structured SQLAlchemy storage: Task 3.
- Three-stage async pipeline: Task 5.
- Gate 1 and Gate 2 through existing agency infrastructure: Task 5.
- Retry and resume state in `PipelineRun.layers_json`: Task 5.
- `DynamicPromptBuilder` and strict JSON templates: Task 4.
- Compatibility snapshots: Task 6.
- Tests and verification: Tasks 1-7.

Type consistency:

- Pydantic `EpisodeScript` lives in `app.models.script`.
- SQLAlchemy `EpisodeScript` lives in `app.db_models` and is imported as `DbEpisodeScript` when both are needed.
- Stage names use `PipelineStage.DRAMATIC_BEATS`, `PipelineStage.SCENE_OUTLINES`, and `PipelineStage.VISUAL_SHOTS`.
- Persistent state uses `layers_json["script_generation"]`.

Scope check:

- The plan does not replace `one_sentence_video_service.py`.
- The plan does not change Pixelle composition.
- The plan does not store or commit API keys.
