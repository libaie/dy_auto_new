# Image Production Strategy Control Plane Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first trusted vertical slice of the image production strategy control plane: strategy CRUD, immutable strategy versions, selection preview, task snapshots, and approved image asset promotion into video production.

**Architecture:** Keep `POST /api/image-creation/tasks` as the only authoritative image execution path. Add a thin `/api/image-production` layer for strategy management, read-only model selection preview, and image asset promotion, reusing `AIModel.config_json`, `ImageCreationTask`, `ImageCreationAsset`, Pixelle submission, existing review records, and video production assets.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Vitest, existing dy_auto API client and Tailwind utility classes.

---

## Source Material

- Spec: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-28-image-production-strategy-control-plane-design.md`
- Eng test plan: `C:\Users\HNXE\.gstack\projects\dy_auto\HNXE-feature-video-review-fixes-eng-review-test-plan-20260528-110920.md`
- Current backend execution path: `server/app/services/image_creation_service.py`
- Current image route: `server/app/routers/image_creation.py`
- Current frontend workbench: `web/src/views/ImageCreationPage.vue`

## Scope

In scope for this plan:

- Strategy tables, policy version table, preview table, and nullable strategy fields on `ImageCreationTask`.
- Default strategy seeds for character anchor, storyboard first frame, and image-to-video input.
- Strategy CRUD APIs with admin-only mutations.
- Selection preview API that explains selected and rejected models.
- Existing image task creation extended with optional strategy fields and immutable snapshots.
- Existing image creation routes protected with `verify_admin_token`.
- Image asset bridge API that promotes only approved image assets into `VideoProductionAsset`.
- Image creation page trust rail and strategy selector.
- Strategy center list/editor view.
- Backend and frontend tests named in the engineering review.

Out of scope for this plan:

- A/B group and attempt execution.
- Automatic strategy mutation from metrics.
- Full policy editor UI.
- Hard provider capacity scheduling beyond displaying preview state.
- Mask painting or image canvas editing.

## File Structure

### Backend

- Create `server/app/services/image_production_strategy_service.py`
  - Owns strategy CRUD, immutable version creation, default seeds, and serialization.
- Create `server/app/services/image_selection_preview_service.py`
  - Owns read-only candidate resolution, selection explanation, request hash, expiry, and preview persistence.
- Create `server/app/services/image_asset_bridge_service.py`
  - Owns approved image asset promotion into `VideoProductionAsset`.
- Create `server/app/routers/image_production.py`
  - Exposes `/api/image-production/strategies`, `/api/image-production/selection-preview`, and `/api/image-production/assets/{asset_id}/promote-to-video-asset`.
- Modify `server/app/db_models.py`
  - Add ORM models and nullable `ImageCreationTask` strategy fields.
- Create `server/alembic/versions/1a2b3c4d5e6f_image_production_strategy_control_plane.py`
  - Adds schema and seed data.
- Modify `server/app/routers/image_creation.py`
  - Add auth dependencies and accept optional strategy/preview fields.
- Modify `server/app/services/image_creation_service.py`
  - Resolve strategy snapshot before Pixelle submission and include it in task payloads.
- Modify `server/app/main.py`
  - Include new `image_production` router.
- Modify `server/tests/conftest.py`
  - Add new tables to cleanup order.

### Frontend

- Create `web/src/api/imageProduction.js`
  - API wrapper for strategy, preview, and bridge calls.
- Modify `web/src/views/ImageCreationPage.vue`
  - Add strategy selector, trust rail, selection preview state, audit details, and task timeline.
- Create `web/src/views/ImageProductionStrategiesPage.vue`
  - Strategy center list/editor MVP.
- Modify `web/src/router/index.js`
  - Add `/image-production/strategies`.
- Modify `web/src/constants/navigation.js`
  - Add AI 视频 navigation item for 图像策略中心.

### Tests

- Create `server/tests/test_image_production_strategy_service.py`
- Create `server/tests/test_image_selection_preview_service.py`
- Create `server/tests/test_image_creation_strategy_snapshot.py`
- Create `server/tests/test_image_asset_bridge.py`
- Create `server/tests/test_image_production_migration.py`
- Modify `server/tests/test_image_creation_mocked_e2e.py`
- Modify `web/src/__tests__/image-creation-page.test.js`
- Create `web/src/__tests__/image-production-strategy-page.test.js`
- Modify `web/src/__tests__/image-creation-a11y.test.js`

---

### Task 1: Add Schema, ORM Models, And Migration Tests

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\db_models.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\alembic\versions\1a2b3c4d5e6f_image_production_strategy_control_plane.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\conftest.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_migration.py`

- [ ] **Step 1: Write the failing migration and table-shape tests**

Create `server/tests/test_image_production_migration.py`:

```python
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect


def test_image_production_revision_depends_on_image_creation_workbench():
    server_dir = Path(__file__).resolve().parents[1]
    config = Config(str(server_dir / "alembic.ini"))
    config.set_main_option("script_location", str(server_dir / "alembic"))
    script = ScriptDirectory.from_config(config)

    revision = script.get_revision("1a2b3c4d5e6f")

    assert revision is not None
    assert revision.down_revision == "e5f6a7b8c9d0"


def test_image_production_tables_exist(test_db):
    inspector = inspect(test_db)

    assert "image_production_strategies" in inspector.get_table_names()
    assert "image_production_strategy_versions" in inspector.get_table_names()
    assert "image_production_policy_versions" in inspector.get_table_names()
    assert "image_selection_previews" in inspector.get_table_names()


def test_image_creation_task_strategy_columns_exist(test_db):
    columns = {column["name"] for column in inspect(test_db).get_columns("image_creation_tasks")}

    assert {
        "strategy_id",
        "strategy_version",
        "strategy_snapshot_json",
        "selection_explanation_json",
        "selection_preview_id",
        "selection_preview_request_hash",
        "fallback_trace_json",
        "queue_job_id",
        "capacity_lease_id",
        "ab_test_group_id",
    }.issubset(columns)
```

- [ ] **Step 2: Run the migration test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py -v
```

Expected: FAIL because the migration revision and ORM tables do not exist.

- [ ] **Step 3: Add ORM models and task extension fields**

Modify `server/app/db_models.py` near the image creation models:

```python
class ImageProductionPolicyVersion(Base):
    __tablename__ = "image_production_policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_type", "name", "version", name="uq_image_policy_version"),
        Index("idx_image_policy_versions_type_status", "policy_type", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    policy_type = Column(String(30), nullable=False)
    name = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ImageProductionStrategy(Base):
    __tablename__ = "image_production_strategies"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_image_strategy_slug"),
        Index("idx_image_strategies_role_status", "destination_role", "status"),
        Index("idx_image_strategies_status_updated", "status", "updated_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    destination_role = Column(String(80), nullable=False)
    supported_modes_json = Column(JSON, nullable=False, default=list)
    default_model_id = Column(String(36), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    fallback_model_ids_json = Column(JSON, nullable=False, default=list)
    common_parameters_json = Column(JSON, nullable=False, default=dict)
    provider_options_json = Column(JSON, nullable=False, default=dict)
    review_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    cost_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    capacity_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    ab_test_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class ImageProductionStrategyVersion(Base):
    __tablename__ = "image_production_strategy_versions"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_image_strategy_version"),
        Index("idx_image_strategy_versions_strategy", "strategy_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class ImageSelectionPreview(Base):
    __tablename__ = "image_selection_previews"
    __table_args__ = (
        Index("idx_image_selection_previews_hash", "request_hash"),
        Index("idx_image_selection_previews_expires", "expires_at"),
        Index("idx_image_selection_previews_user_created", "user_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    mode = Column(String(40), nullable=False)
    destination_role = Column(String(80), nullable=True)
    model_id = Column(String(36), nullable=True)
    selected_model_id = Column(String(36), nullable=True)
    request_hash = Column(String(64), nullable=False)
    response_json = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
```

Add these nullable columns to `ImageCreationTask`:

```python
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="SET NULL"), nullable=True)
    strategy_version = Column(Integer, nullable=True)
    strategy_snapshot_json = Column(JSON, nullable=True, default=dict)
    selection_explanation_json = Column(JSON, nullable=True, default=dict)
    selection_preview_id = Column(String(36), ForeignKey("image_selection_previews.id", ondelete="SET NULL"), nullable=True)
    selection_preview_request_hash = Column(String(64), nullable=True)
    fallback_trace_json = Column(JSON, nullable=True, default=dict)
    queue_job_id = Column(String(36), nullable=True)
    capacity_lease_id = Column(String(80), nullable=True)
    ab_test_group_id = Column(String(36), nullable=True)
```

Add indexes to `ImageCreationTask.__table_args__`:

```python
        Index("idx_image_tasks_strategy", "strategy_id", "strategy_version"),
        Index("idx_image_tasks_selection_preview", "selection_preview_id"),
```

- [ ] **Step 4: Add the Alembic migration**

Create `server/alembic/versions/1a2b3c4d5e6f_image_production_strategy_control_plane.py`:

```python
"""image production strategy control plane

Revision ID: 1a2b3c4d5e6f
Revises: e5f6a7b8c9d0
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa


revision = "1a2b3c4d5e6f"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_production_policy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_type", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_type", "name", "version", name="uq_image_policy_version"),
    )
    op.create_index("idx_image_policy_versions_type_status", "image_production_policy_versions", ["policy_type", "status"])

    op.create_table(
        "image_production_strategies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("destination_role", sa.String(length=80), nullable=False),
        sa.Column("supported_modes_json", sa.JSON(), nullable=False),
        sa.Column("default_model_id", sa.String(length=36), nullable=True),
        sa.Column("fallback_model_ids_json", sa.JSON(), nullable=False),
        sa.Column("common_parameters_json", sa.JSON(), nullable=False),
        sa.Column("provider_options_json", sa.JSON(), nullable=False),
        sa.Column("review_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("cost_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("capacity_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("ab_test_policy_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["default_model_id"], ["ai_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["review_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cost_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["capacity_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ab_test_policy_version_id"], ["image_production_policy_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_image_strategy_slug"),
    )
    op.create_index("idx_image_strategies_role_status", "image_production_strategies", ["destination_role", "status"])
    op.create_index("idx_image_strategies_status_updated", "image_production_strategies", ["status", "updated_at"])

    op.create_table(
        "image_production_strategy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("strategy_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["image_production_strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "version", name="uq_image_strategy_version"),
    )
    op.create_index("idx_image_strategy_versions_strategy", "image_production_strategy_versions", ["strategy_id"])

    op.create_table(
        "image_selection_previews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_id", sa.String(length=36), nullable=True),
        sa.Column("strategy_version", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("destination_role", sa.String(length=80), nullable=True),
        sa.Column("model_id", sa.String(length=36), nullable=True),
        sa.Column("selected_model_id", sa.String(length=36), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["image_production_strategies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_image_selection_previews_hash", "image_selection_previews", ["request_hash"])
    op.create_index("idx_image_selection_previews_expires", "image_selection_previews", ["expires_at"])
    op.create_index("idx_image_selection_previews_user_created", "image_selection_previews", ["user_id", "created_at"])

    with op.batch_alter_table("image_creation_tasks") as batch_op:
        batch_op.add_column(sa.Column("strategy_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("strategy_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("strategy_snapshot_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("selection_explanation_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("selection_preview_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("selection_preview_request_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("fallback_trace_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("queue_job_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("capacity_lease_id", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("ab_test_group_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_image_tasks_strategy_id", "image_production_strategies", ["strategy_id"], ["id"], ondelete="SET NULL")
        batch_op.create_foreign_key("fk_image_tasks_selection_preview_id", "image_selection_previews", ["selection_preview_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("idx_image_tasks_strategy", ["strategy_id", "strategy_version"])
        batch_op.create_index("idx_image_tasks_selection_preview", ["selection_preview_id"])


def downgrade() -> None:
    with op.batch_alter_table("image_creation_tasks") as batch_op:
        batch_op.drop_index("idx_image_tasks_selection_preview")
        batch_op.drop_index("idx_image_tasks_strategy")
        batch_op.drop_constraint("fk_image_tasks_selection_preview_id", type_="foreignkey")
        batch_op.drop_constraint("fk_image_tasks_strategy_id", type_="foreignkey")
        batch_op.drop_column("ab_test_group_id")
        batch_op.drop_column("capacity_lease_id")
        batch_op.drop_column("queue_job_id")
        batch_op.drop_column("fallback_trace_json")
        batch_op.drop_column("selection_preview_request_hash")
        batch_op.drop_column("selection_preview_id")
        batch_op.drop_column("selection_explanation_json")
        batch_op.drop_column("strategy_snapshot_json")
        batch_op.drop_column("strategy_version")
        batch_op.drop_column("strategy_id")

    op.drop_index("idx_image_selection_previews_user_created", table_name="image_selection_previews")
    op.drop_index("idx_image_selection_previews_expires", table_name="image_selection_previews")
    op.drop_index("idx_image_selection_previews_hash", table_name="image_selection_previews")
    op.drop_table("image_selection_previews")

    op.drop_index("idx_image_strategy_versions_strategy", table_name="image_production_strategy_versions")
    op.drop_table("image_production_strategy_versions")

    op.drop_index("idx_image_strategies_status_updated", table_name="image_production_strategies")
    op.drop_index("idx_image_strategies_role_status", table_name="image_production_strategies")
    op.drop_table("image_production_strategies")

    op.drop_index("idx_image_policy_versions_type_status", table_name="image_production_policy_versions")
    op.drop_table("image_production_policy_versions")
```

- [ ] **Step 5: Update test cleanup tables**

Modify the import list in `server/tests/conftest.py` to include:

```python
ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion, ImageSelectionPreview
```

Add these models before `ImageCreationTask` in `_CLEANUP_TABLES`:

```python
    ImageSelectionPreview, ImageProductionStrategyVersion, ImageProductionStrategy, ImageProductionPolicyVersion,
```

- [ ] **Step 6: Run the migration test to verify it passes**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit schema changes**

```powershell
git add server/app/db_models.py server/alembic/versions/1a2b3c4d5e6f_image_production_strategy_control_plane.py server/tests/conftest.py server/tests/test_image_production_migration.py
git commit -m "feat: add image production strategy schema"
```

---

### Task 2: Implement Strategy Service, Seeds, And CRUD API

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_production_strategy_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\main.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_production_strategy_service.py`

- [ ] **Step 1: Write the failing strategy service/API tests**

Create `server/tests/test_image_production_strategy_service.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import ImageProductionStrategy, ImageProductionStrategyVersion
from app.main import app
from app.services.image_production_strategy_service import seed_default_image_strategies


client = TestClient(app)


def test_seed_default_image_strategies_is_idempotent(db):
    seed_default_image_strategies(db)
    seed_default_image_strategies(db)

    strategies = db.query(ImageProductionStrategy).order_by(ImageProductionStrategy.slug.asc()).all()

    assert [strategy.slug for strategy in strategies] == [
        "character-anchor-default",
        "image-to-video-input-default",
        "storyboard-first-frame-default",
    ]
    assert db.query(ImageProductionStrategyVersion).count() == 3


def test_create_strategy_writes_initial_version(db):
    resp = client.post("/api/image-production/strategies", json={
        "slug": "test-storyboard",
        "name": "测试分镜首帧",
        "description": "用于分镜首帧",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
        "default_model_id": None,
        "fallback_model_ids": [],
        "common_parameters": {"size": "1024x1024"},
        "provider_options": {},
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["strategy"]["slug"] == "test-storyboard"
    assert body["strategy"]["version"] == 1
    assert db.query(ImageProductionStrategyVersion).count() == 1


def test_update_strategy_requires_current_version(db):
    created = client.post("/api/image-production/strategies", json={
        "slug": "conflict-test",
        "name": "冲突测试",
        "destination_role": "image_to_video_input",
        "supported_modes": ["image_to_image"],
    }).json()["strategy"]

    conflict = client.put(f"/api/image-production/strategies/{created['id']}", json={
        "version": created["version"] - 1,
        "name": "过期保存",
        "description": "",
        "destination_role": "image_to_video_input",
        "supported_modes": ["image_to_image"],
        "default_model_id": None,
        "fallback_model_ids": [],
        "common_parameters": {},
        "provider_options": {},
    })

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IMAGE_STRATEGY_VERSION_CONFLICT"


def test_archived_strategy_is_not_listed_as_active(db):
    strategy = client.post("/api/image-production/strategies", json={
        "slug": "archive-test",
        "name": "归档测试",
        "destination_role": "character_anchor_image",
        "supported_modes": ["text_to_image"],
    }).json()["strategy"]

    archived = client.post(f"/api/image-production/strategies/{strategy['id']}/archive")
    listed = client.get("/api/image-production/strategies?status=active")

    assert archived.status_code == 200
    assert all(row["id"] != strategy["id"] for row in listed.json()["strategies"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_strategy_service.py -v
```

Expected: FAIL because the service and route do not exist.

- [ ] **Step 3: Implement strategy service**

Create `server/app/services/image_production_strategy_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ImageProductionPolicyVersion, ImageProductionStrategy, ImageProductionStrategyVersion
from app.services.image_creation_errors import image_error


VALID_DESTINATION_ROLES = {
    "character_anchor_image",
    "scene_reference_image",
    "style_reference_image",
    "storyboard_first_frame",
    "image_to_video_input",
    "repaint_image",
    "fusion_image",
    "batch_story_images",
}
VALID_STATUSES = {"active", "archived", "disabled"}


DEFAULT_STRATEGIES = [
    {
        "slug": "character-anchor-default",
        "name": "默认角色锚定图",
        "description": "用于生成角色多角度身份参考图。",
        "destination_role": "character_anchor_image",
        "supported_modes": ["text_to_image", "text_to_image_set"],
        "common_parameters": {"count": 4},
        "provider_options": {},
    },
    {
        "slug": "storyboard-first-frame-default",
        "name": "默认分镜首帧",
        "description": "用于生成分镜镜头首帧。",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image", "image_to_image"],
        "common_parameters": {"count": 1},
        "provider_options": {},
    },
    {
        "slug": "image-to-video-input-default",
        "name": "默认图生视频输入图",
        "description": "用于生成进入图生视频阶段前的已审查输入图。",
        "destination_role": "image_to_video_input",
        "supported_modes": ["image_to_image", "multi_reference_to_image"],
        "common_parameters": {"count": 1},
        "provider_options": {},
    },
]


def _default_policy(db: Session, policy_type: str, name: str, snapshot: dict[str, Any]) -> ImageProductionPolicyVersion:
    existing = db.query(ImageProductionPolicyVersion).filter(
        ImageProductionPolicyVersion.policy_type == policy_type,
        ImageProductionPolicyVersion.name == name,
        ImageProductionPolicyVersion.version == 1,
    ).first()
    if existing:
        return existing
    policy = ImageProductionPolicyVersion(
        policy_type=policy_type,
        name=name,
        version=1,
        snapshot_json=snapshot,
        status="active",
    )
    db.add(policy)
    db.flush()
    return policy


def _strategy_snapshot(strategy: ImageProductionStrategy) -> dict[str, Any]:
    return {
        "id": strategy.id,
        "slug": strategy.slug,
        "name": strategy.name,
        "description": strategy.description or "",
        "destination_role": strategy.destination_role,
        "supported_modes": strategy.supported_modes_json or [],
        "default_model_id": strategy.default_model_id,
        "fallback_model_ids": strategy.fallback_model_ids_json or [],
        "common_parameters": strategy.common_parameters_json or {},
        "provider_options": strategy.provider_options_json or {},
        "review_policy_version_id": strategy.review_policy_version_id,
        "cost_policy_version_id": strategy.cost_policy_version_id,
        "capacity_policy_version_id": strategy.capacity_policy_version_id,
        "ab_test_policy_version_id": strategy.ab_test_policy_version_id,
        "status": strategy.status,
        "version": strategy.version,
    }


def _write_version(db: Session, strategy: ImageProductionStrategy) -> ImageProductionStrategyVersion:
    version = ImageProductionStrategyVersion(
        strategy_id=strategy.id,
        version=strategy.version,
        snapshot_json=_strategy_snapshot(strategy),
    )
    db.add(version)
    db.flush()
    return version


def strategy_payload(strategy: ImageProductionStrategy) -> dict[str, Any]:
    return {
        "id": strategy.id,
        "slug": strategy.slug,
        "name": strategy.name,
        "description": strategy.description or "",
        "destination_role": strategy.destination_role,
        "supported_modes": strategy.supported_modes_json or [],
        "default_model_id": strategy.default_model_id,
        "fallback_model_ids": strategy.fallback_model_ids_json or [],
        "common_parameters": strategy.common_parameters_json or {},
        "provider_options": strategy.provider_options_json or {},
        "status": strategy.status,
        "version": strategy.version,
        "created_at": strategy.created_at.isoformat() if strategy.created_at else None,
        "updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
    }


def validate_strategy_input(payload: dict[str, Any]) -> None:
    role = payload.get("destination_role")
    if role not in VALID_DESTINATION_ROLES:
        raise image_error(422, "IMAGE_STRATEGY_ROLE_INVALID", "Strategy destination role is invalid.", "Choose a supported role.", retryable=False)
    modes = payload.get("supported_modes") or []
    if not isinstance(modes, list) or not modes:
        raise image_error(422, "IMAGE_STRATEGY_MODES_REQUIRED", "Strategy must support at least one mode.", "Choose at least one mode.", retryable=False)


def seed_default_image_strategies(db: Session) -> None:
    review_policy = _default_policy(db, "review", "default-image-review", {"manual_required_for": ["image_to_video_input"]})
    cost_policy = _default_policy(db, "cost", "default-image-cost", {"confirmation_threshold_amount": 1})
    capacity_policy = _default_policy(db, "capacity", "default-image-capacity", {"mode": "preview_only"})
    for item in DEFAULT_STRATEGIES:
        existing = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.slug == item["slug"]).first()
        if existing:
            continue
        strategy = ImageProductionStrategy(
            slug=item["slug"],
            name=item["name"],
            description=item["description"],
            destination_role=item["destination_role"],
            supported_modes_json=item["supported_modes"],
            default_model_id=None,
            fallback_model_ids_json=[],
            common_parameters_json=item["common_parameters"],
            provider_options_json=item["provider_options"],
            review_policy_version_id=review_policy.id,
            cost_policy_version_id=cost_policy.id,
            capacity_policy_version_id=capacity_policy.id,
            status="active",
            version=1,
        )
        db.add(strategy)
        db.flush()
        _write_version(db, strategy)
    db.commit()


def list_strategies(db: Session, status: str | None = None, destination_role: str | None = None) -> list[ImageProductionStrategy]:
    query = db.query(ImageProductionStrategy)
    if status:
        query = query.filter(ImageProductionStrategy.status == status)
    if destination_role:
        query = query.filter(ImageProductionStrategy.destination_role == destination_role)
    return query.order_by(ImageProductionStrategy.destination_role.asc(), ImageProductionStrategy.name.asc()).all()


def get_strategy(db: Session, strategy_id: str) -> ImageProductionStrategy:
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(404, "IMAGE_STRATEGY_NOT_FOUND", "Image production strategy was not found.", "Choose another strategy.", retryable=False)
    return strategy


def create_strategy(db: Session, payload: dict[str, Any]) -> ImageProductionStrategy:
    validate_strategy_input(payload)
    strategy = ImageProductionStrategy(
        slug=payload["slug"],
        name=payload["name"],
        description=payload.get("description") or "",
        destination_role=payload["destination_role"],
        supported_modes_json=payload.get("supported_modes") or [],
        default_model_id=payload.get("default_model_id"),
        fallback_model_ids_json=payload.get("fallback_model_ids") or [],
        common_parameters_json=payload.get("common_parameters") or {},
        provider_options_json=payload.get("provider_options") or {},
        status="active",
        version=1,
    )
    db.add(strategy)
    try:
        db.flush()
        _write_version(db, strategy)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise image_error(409, "IMAGE_STRATEGY_SLUG_CONFLICT", "Strategy slug already exists.", "Use a unique strategy slug.", retryable=False) from exc
    db.refresh(strategy)
    return strategy


def update_strategy(db: Session, strategy_id: str, payload: dict[str, Any]) -> ImageProductionStrategy:
    validate_strategy_input(payload)
    strategy = get_strategy(db, strategy_id)
    if int(payload.get("version") or 0) != strategy.version:
        raise image_error(409, "IMAGE_STRATEGY_VERSION_CONFLICT", "Strategy was changed by another editor.", "Reload the strategy and apply your changes again.", retryable=False)
    strategy.name = payload["name"]
    strategy.description = payload.get("description") or ""
    strategy.destination_role = payload["destination_role"]
    strategy.supported_modes_json = payload.get("supported_modes") or []
    strategy.default_model_id = payload.get("default_model_id")
    strategy.fallback_model_ids_json = payload.get("fallback_model_ids") or []
    strategy.common_parameters_json = payload.get("common_parameters") or {}
    strategy.provider_options_json = payload.get("provider_options") or {}
    strategy.version += 1
    strategy.updated_at = bj_now()
    _write_version(db, strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


def set_strategy_status(db: Session, strategy_id: str, status: str) -> ImageProductionStrategy:
    if status not in VALID_STATUSES:
        raise image_error(422, "IMAGE_STRATEGY_STATUS_INVALID", "Strategy status is invalid.", "Choose active, disabled, or archived.", retryable=False)
    strategy = get_strategy(db, strategy_id)
    strategy.status = status
    strategy.updated_at = bj_now()
    db.commit()
    db.refresh(strategy)
    return strategy
```

- [ ] **Step 4: Implement router and register it**

Create `server/app/routers/image_production.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token
from app.services.image_production_strategy_service import (
    create_strategy,
    get_strategy,
    list_strategies,
    seed_default_image_strategies,
    set_strategy_status,
    strategy_payload,
    update_strategy,
)


router = APIRouter(prefix="/api/image-production", tags=["image-production"])


class StrategyRequest(BaseModel):
    slug: str | None = None
    name: str
    description: str = ""
    destination_role: str
    supported_modes: list[str] = Field(default_factory=list)
    default_model_id: str | None = None
    fallback_model_ids: list[str] = Field(default_factory=list)
    common_parameters: dict = Field(default_factory=dict)
    provider_options: dict = Field(default_factory=dict)
    version: int | None = None


@router.post("/strategies/seed-defaults")
def seed_defaults(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    seed_default_image_strategies(db)
    return {"ok": True}


@router.get("/strategies")
def strategies(
    status: str | None = Query(None),
    destination_role: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(verify_admin_token),
):
    rows = list_strategies(db, status=status, destination_role=destination_role)
    return {"ok": True, "strategies": [strategy_payload(row) for row in rows]}


@router.post("/strategies")
def create(body: StrategyRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    payload = body.model_dump()
    if not payload.get("slug"):
        payload["slug"] = payload["name"].strip().lower().replace(" ", "-")
    strategy = create_strategy(db, payload)
    return {"ok": True, "strategy": strategy_payload(strategy)}


@router.get("/strategies/{strategy_id}")
def read(strategy_id: str, db: Session = Depends(get_db), _=Depends(verify_admin_token)):
    return {"ok": True, "strategy": strategy_payload(get_strategy(db, strategy_id))}


@router.put("/strategies/{strategy_id}")
def update(strategy_id: str, body: StrategyRequest, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    strategy = update_strategy(db, strategy_id, body.model_dump())
    return {"ok": True, "strategy": strategy_payload(strategy)}


@router.post("/strategies/{strategy_id}/activate")
def activate(strategy_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return {"ok": True, "strategy": strategy_payload(set_strategy_status(db, strategy_id, "active"))}


@router.post("/strategies/{strategy_id}/archive")
def archive(strategy_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return {"ok": True, "strategy": strategy_payload(set_strategy_status(db, strategy_id, "archived"))}
```

Modify `server/app/main.py`:

```python
from app.routers import image_creation, image_production
```

Register after `image_creation` or near other AI-video routers:

```python
app.include_router(image_production.router)
```

- [ ] **Step 5: Run strategy tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_strategy_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit strategy CRUD**

```powershell
git add server/app/services/image_production_strategy_service.py server/app/routers/image_production.py server/app/main.py server/tests/test_image_production_strategy_service.py
git commit -m "feat: add image production strategy API"
```

---

### Task 3: Implement Selection Preview Service And API

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_selection_preview_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_selection_preview_service.py`

- [ ] **Step 1: Write failing selection preview tests**

Create `server/tests/test_image_selection_preview_service.py`:

```python
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db_models import AIModel, ImageSelectionPreview
from app.main import app
from app.services.crypto import encrypt
from app.services.image_production_strategy_service import create_strategy


client = TestClient(app)


def _seed_image_model(db, *, name, scene_key, capabilities, sort_order=0):
    model = AIModel(
        name=name,
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret"),
        model_name=f"mock-{uuid4().hex}",
        enabled=True,
        sort_order=sort_order,
        config_json={
            "scene_key": scene_key,
            "scene_keys": [scene_key],
            "capabilities": capabilities,
            "limits": {"max_output_images": 4, "max_reference_images": 4},
            "provider_options_schema": {"watermark": {"type": "boolean"}},
            "config_version": 1,
        },
    )
    db.add(model)
    db.commit()
    return model


def test_selection_preview_selects_strategy_default_model(db):
    model = _seed_image_model(db, name="selected", scene_key="image_generation", capabilities={"text_to_image": True})
    strategy = create_strategy(db, {
        "slug": "preview-default",
        "name": "预览默认",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
        "default_model_id": model.id,
    })

    resp = client.post("/api/image-production/selection-preview", json={
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "count": 1,
        "provider_options": {"watermark": True},
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["selected_model"]["model_id"] == model.id
    assert body["selection_explanation"]["selected_reason"] == "strategy_default_model"
    assert body["request_hash"]
    assert db.query(ImageSelectionPreview).count() == 1


def test_selection_preview_records_rejected_candidates(db):
    _seed_image_model(db, name="wrong", scene_key="image_generation", capabilities={"text_to_image": False}, sort_order=0)
    selected = _seed_image_model(db, name="right", scene_key="image_generation", capabilities={"text_to_image": True}, sort_order=1)

    resp = client.post("/api/image-production/selection-preview", json={
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "count": 1,
    })

    assert resp.status_code == 200
    explanation = resp.json()["selection_explanation"]
    assert resp.json()["selected_model"]["model_id"] == selected.id
    assert explanation["rejected_candidates"][0]["reason"] == "capability_not_supported"


def test_selection_preview_rejects_unsupported_provider_option(db):
    _seed_image_model(db, name="right", scene_key="image_generation", capabilities={"text_to_image": True})

    resp = client.post("/api/image-production/selection-preview", json={
        "mode": "text_to_image",
        "destination_role": "storyboard_first_frame",
        "provider_options": {"api_key": "leak"},
    })

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "IMAGE_PROVIDER_OPTIONS_INVALID"
```

- [ ] **Step 2: Run preview tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_selection_preview_service.py -v
```

Expected: FAIL because `image_selection_preview_service.py` and endpoint are missing.

- [ ] **Step 3: Implement the preview service**

Create `server/app/services/image_selection_preview_service.py`:

```python
from __future__ import annotations

from datetime import timedelta
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import AIModel, ImageProductionStrategy, ImageSelectionPreview
from app.services.image_creation_errors import image_error
from app.services.image_creation_service import MODE_TO_SCENE_CAPABILITY, PROTECTED_PROVIDER_OPTION_KEYS


def _preview_hash(payload: dict[str, Any]) -> str:
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(stable).hexdigest()


def _model_supports(model: AIModel, scene_key: str, capability_key: str) -> bool:
    config = model.config_json or {}
    scene_keys = config.get("scene_keys")
    if not isinstance(scene_keys, list):
        scene_keys = [config.get("scene_key")]
    if scene_key not in scene_keys:
        return False
    capabilities = config.get("capabilities") or {}
    by_scene = config.get("capabilities_by_scene") or {}
    if isinstance(by_scene.get(scene_key), dict):
        return bool(by_scene[scene_key].get(capability_key))
    return bool(capabilities.get(capability_key)) or (scene_key == "image_generation" and capability_key == "text_to_image")


def _validate_provider_options(provider_options: dict[str, Any], model: AIModel) -> None:
    schema = ((model.config_json or {}).get("provider_options_schema") or {})
    unknown = set(provider_options) - set(schema)
    protected = set(provider_options) & PROTECTED_PROVIDER_OPTION_KEYS
    if unknown or protected:
        raise image_error(
            400,
            "IMAGE_PROVIDER_OPTIONS_INVALID",
            "Provider options contain unsupported fields.",
            "Use only the options exposed by the selected model configuration.",
            retryable=False,
        )


def _strategy(db: Session, strategy_id: str | None) -> ImageProductionStrategy | None:
    if not strategy_id:
        return None
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(404, "IMAGE_STRATEGY_NOT_FOUND", "Image production strategy was not found.", "Choose another strategy.", retryable=False)
    if strategy.status != "active":
        raise image_error(409, "IMAGE_STRATEGY_ARCHIVED", "Strategy is not active.", "Choose an active strategy.", retryable=False)
    return strategy


def create_selection_preview(db: Session, payload: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    mode = payload.get("mode")
    if mode not in MODE_TO_SCENE_CAPABILITY:
        raise image_error(400, "IMAGE_MODE_UNSUPPORTED", "Unsupported image mode.", "Choose a supported image mode.", retryable=False)
    scene_key, capability_key, output_mode = MODE_TO_SCENE_CAPABILITY[mode]
    strategy = _strategy(db, payload.get("strategy_id"))
    if strategy and payload.get("strategy_version") and int(payload["strategy_version"]) != strategy.version:
        raise image_error(409, "IMAGE_STRATEGY_VERSION_CONFLICT", "Strategy version is stale.", "Reload strategy preview.", retryable=False)
    if strategy and mode not in (strategy.supported_modes_json or []):
        raise image_error(422, "IMAGE_STRATEGY_MODE_UNSUPPORTED", "Strategy does not support this mode.", "Choose another strategy or mode.", retryable=False)

    models = db.query(AIModel).filter(AIModel.enabled == True, AIModel.model_type == "image").order_by(AIModel.sort_order.asc(), AIModel.created_at.asc()).all()
    selected = None
    rejected: list[dict[str, Any]] = []
    default_model_id = payload.get("model_id") or (strategy.default_model_id if strategy else None)
    for model in models:
        if default_model_id and model.id != default_model_id:
            rejected.append({"model_id": model.id, "name": model.name, "reason": "not_strategy_default"})
            continue
        if not _model_supports(model, scene_key, capability_key):
            rejected.append({"model_id": model.id, "name": model.name, "reason": "capability_not_supported"})
            continue
        selected = model
        break
    if not selected:
        raise image_error(422, "IMAGE_MODEL_SELECTION_EMPTY", "No enabled model supports this image request.", "Configure a compatible image model.", retryable=False)
    _validate_provider_options(payload.get("provider_options") or {}, selected)

    request_hash = _preview_hash({
        "mode": mode,
        "destination_role": payload.get("destination_role"),
        "strategy_id": strategy.id if strategy else None,
        "strategy_version": strategy.version if strategy else None,
        "model_id": selected.id,
        "count": payload.get("count") or 1,
        "provider_options": payload.get("provider_options") or {},
    })
    explanation = {
        "requested_mode": mode,
        "requested_destination_role": payload.get("destination_role"),
        "strategy_id": strategy.id if strategy else None,
        "strategy_version": strategy.version if strategy else None,
        "candidate_count": len(models),
        "rejected_candidates": rejected,
        "selected_model_id": selected.id,
        "selected_reason": "strategy_default_model" if strategy and strategy.default_model_id == selected.id else "first_supported_model",
    }
    response = {
        "ok": True,
        "selected_model": {
            "model_id": selected.id,
            "name": selected.name,
            "provider": selected.provider,
            "model_name": selected.model_name,
            "config_version": (selected.config_json or {}).get("config_version", 1),
        },
        "strategy": {
            "id": strategy.id,
            "version": strategy.version,
            "name": strategy.name,
            "destination_role": strategy.destination_role,
        } if strategy else None,
        "selection_explanation": explanation,
        "cost_estimate": {"amount": float(payload.get("count") or 1), "currency": "CNY", "estimate_source": "local_policy"},
        "request_hash": request_hash,
        "warnings": [],
    }
    preview = ImageSelectionPreview(
        user_id=user_id,
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        mode=mode,
        destination_role=payload.get("destination_role"),
        model_id=payload.get("model_id"),
        selected_model_id=selected.id,
        request_hash=request_hash,
        response_json=response,
        expires_at=bj_now() + timedelta(minutes=15),
    )
    db.add(preview)
    db.commit()
    db.refresh(preview)
    response["selection_preview_id"] = preview.id
    response["expires_at"] = preview.expires_at.isoformat()
    return response
```

- [ ] **Step 4: Add the preview route**

Modify `server/app/routers/image_production.py`:

```python
from app.services.image_selection_preview_service import create_selection_preview


class SelectionPreviewRequest(BaseModel):
    mode: str
    destination_role: str | None = None
    strategy_id: str | None = None
    strategy_version: int | None = None
    model_id: str | None = None
    source_asset_ids: list[str] = Field(default_factory=list)
    reference_asset_ids: list[str] = Field(default_factory=list)
    common_parameters: dict = Field(default_factory=dict)
    provider_options: dict = Field(default_factory=dict)
    output_format: str | None = None
    count: int = 1
    reference_count: int = 0


@router.post("/selection-preview")
def selection_preview(body: SelectionPreviewRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
    user_id = user[0] if isinstance(user, tuple) else None
    return create_selection_preview(db, body.model_dump(), user_id=user_id)
```

- [ ] **Step 5: Run selection preview tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_selection_preview_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit selection preview**

```powershell
git add server/app/services/image_selection_preview_service.py server/app/routers/image_production.py server/tests/test_image_selection_preview_service.py
git commit -m "feat: add image model selection preview"
```

---

### Task 4: Extend Image Task Creation With Strategy Snapshots And Auth

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_creation.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_creation_service.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_strategy_snapshot.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_creation_mocked_e2e.py`

- [ ] **Step 1: Write failing strategy snapshot tests**

Create `server/tests/test_image_creation_strategy_snapshot.py`:

```python
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db_models import AIModel, ImageCreationTask
from app.main import app
from app.services.crypto import encrypt
from app.services.image_production_strategy_service import create_strategy


client = TestClient(app)


def _seed_model(db):
    model = AIModel(
        name=f"snapshot-model-{uuid4().hex}",
        model_type="image",
        provider="mock",
        base_url="http://pixelle.test",
        api_key=encrypt("secret-key"),
        model_name=f"mock-{uuid4().hex}",
        enabled=True,
        config_json={
            "scene_key": "image_generation",
            "scene_keys": ["image_generation"],
            "capabilities": {"text_to_image": True},
            "provider_options_schema": {"watermark": {"type": "boolean"}},
            "config_version": 7,
            "secret_config_key": "must-not-leak",
        },
    )
    db.add(model)
    db.commit()
    return model


def test_create_image_task_with_strategy_persists_snapshot(db, monkeypatch):
    model = _seed_model(db)
    strategy = create_strategy(db, {
        "slug": "snapshot-strategy",
        "name": "快照策略",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
        "default_model_id": model.id,
        "common_parameters": {"size": "1024x1024"},
        "provider_options": {"watermark": True},
    })

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "snapshot-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "cinematic first frame",
        "count": 1,
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "destination_role": "storyboard_first_frame",
        "provider_options": {"watermark": True},
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    task = db.query(ImageCreationTask).filter(ImageCreationTask.id == resp.json()["task"]["id"]).first()
    assert task.strategy_id == strategy.id
    assert task.strategy_version == strategy.version
    assert task.strategy_snapshot_json["slug"] == "snapshot-strategy"
    assert task.selection_explanation_json["selected_model_id"] == model.id
    assert "secret" not in str(task.model_trace_json).lower()


def test_create_image_task_without_strategy_still_works(db, monkeypatch):
    _seed_model(db)

    async def fake_submit(**kwargs):
        return {"ok": True, "stage_task_id": "no-strategy-stage"}

    monkeypatch.setattr("app.services.image_creation_service.submit_image_create", fake_submit)

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "existing path",
        "count": 1,
        "cost_confirmation": True,
    })

    assert resp.status_code == 200
    assert resp.json()["task"]["strategy"] is None


def test_create_image_task_rejects_stale_strategy_version(db):
    strategy = create_strategy(db, {
        "slug": "stale-strategy",
        "name": "过期策略",
        "destination_role": "storyboard_first_frame",
        "supported_modes": ["text_to_image"],
    })

    resp = client.post("/api/image-creation/tasks", json={
        "mode": "text_to_image",
        "prompt": "stale",
        "strategy_id": strategy.id,
        "strategy_version": strategy.version - 1,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "IMAGE_STRATEGY_VERSION_CONFLICT"
```

- [ ] **Step 2: Run snapshot tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_strategy_snapshot.py -v
```

Expected: FAIL because `CreateImageTaskRequest` and `create_image_task` do not handle strategy fields.

- [ ] **Step 3: Add auth and request fields to image creation router**

Modify `server/app/routers/image_creation.py` imports:

```python
from app.deps import verify_admin_token
```

Add fields to `CreateImageTaskRequest` and `EditImageAssetRequest`:

```python
    strategy_id: str | None = None
    strategy_version: int | None = None
    selection_preview_id: str | None = None
    selection_preview_request_hash: str | None = None
```

Add `user=Depends(verify_admin_token)` to all admin-facing image creation route signatures:

```python
async def create_task(body: CreateImageTaskRequest, db: Session = Depends(get_db), user=Depends(verify_admin_token)):
```

Pass user id into task payload:

```python
    payload = body.model_dump()
    if isinstance(user, tuple):
        payload["user_id"] = user[0]
    task = await create_image_task(db, payload)
```

Repeat the same dependency for:

- `upload_image`
- `read_task`
- `sync_task`
- `assets`
- `review_asset`
- `edit_asset`

- [ ] **Step 4: Add strategy resolution helpers to image creation service**

Modify `server/app/services/image_creation_service.py` imports:

```python
from app.db_models import ImageProductionStrategy, ImageSelectionPreview
```

Add helpers near `normalized_request_hash`:

```python
def _resolve_strategy_snapshot(db: Session, payload: dict[str, Any], mode: str) -> tuple[ImageProductionStrategy | None, dict[str, Any], dict[str, Any]]:
    strategy_id = payload.get("strategy_id")
    if not strategy_id:
        return None, {}, {}
    strategy = db.query(ImageProductionStrategy).filter(ImageProductionStrategy.id == strategy_id).first()
    if not strategy:
        raise image_error(404, "IMAGE_STRATEGY_NOT_FOUND", "Image production strategy was not found.", "Choose another strategy.", retryable=False)
    if strategy.status != "active":
        raise image_error(409, "IMAGE_STRATEGY_ARCHIVED", "Strategy is not active.", "Choose an active strategy.", retryable=False)
    if payload.get("strategy_version") and int(payload["strategy_version"]) != strategy.version:
        raise image_error(409, "IMAGE_STRATEGY_VERSION_CONFLICT", "Strategy version is stale.", "Reload strategy preview.", retryable=False)
    if mode not in (strategy.supported_modes_json or []):
        raise image_error(422, "IMAGE_STRATEGY_MODE_UNSUPPORTED", "Strategy does not support this image mode.", "Choose another strategy or mode.", retryable=False)
    snapshot = {
        "id": strategy.id,
        "slug": strategy.slug,
        "name": strategy.name,
        "destination_role": strategy.destination_role,
        "supported_modes": strategy.supported_modes_json or [],
        "default_model_id": strategy.default_model_id,
        "fallback_model_ids": strategy.fallback_model_ids_json or [],
        "common_parameters": strategy.common_parameters_json or {},
        "provider_options": strategy.provider_options_json or {},
        "version": strategy.version,
    }
    explanation = {
        "strategy_id": strategy.id,
        "strategy_version": strategy.version,
        "selected_model_id": payload.get("model_id") or strategy.default_model_id,
        "selected_reason": "strategy_default_model" if strategy.default_model_id and not payload.get("model_id") else "manual_or_existing_resolution",
    }
    return strategy, snapshot, explanation


def _validate_selection_preview(db: Session, payload: dict[str, Any]) -> None:
    preview_id = payload.get("selection_preview_id")
    if not preview_id:
        return
    preview = db.query(ImageSelectionPreview).filter(ImageSelectionPreview.id == preview_id).first()
    if not preview:
        raise image_error(404, "IMAGE_SELECTION_PREVIEW_NOT_FOUND", "Selection preview was not found.", "Run selection preview again.", retryable=False)
    if payload.get("selection_preview_request_hash") and preview.request_hash != payload["selection_preview_request_hash"]:
        raise image_error(409, "IMAGE_SELECTION_PREVIEW_DRIFT", "Selection preview no longer matches this request.", "Run selection preview again.", retryable=False)
    if preview.expires_at < bj_now():
        raise image_error(409, "IMAGE_SELECTION_PREVIEW_EXPIRED", "Selection preview expired.", "Run selection preview again.", retryable=False)
```

- [ ] **Step 5: Apply strategy fields in `create_image_task`**

In `create_image_task`, after `_validate_payload(payload)`:

```python
    strategy, strategy_snapshot, selection_explanation = _resolve_strategy_snapshot(db, payload, payload["mode"])
    _validate_selection_preview(db, payload)
    if strategy and not payload.get("model_id") and strategy.default_model_id:
        payload["model_id"] = strategy.default_model_id
    if strategy:
        merged_provider_options = dict(strategy.provider_options_json or {})
        merged_provider_options.update(payload.get("provider_options") or {})
        payload["provider_options"] = merged_provider_options
        for key, value in (strategy.common_parameters_json or {}).items():
            payload.setdefault(key, value)
```

In the `ImageCreationTask(...)` constructor, add:

```python
        user_id=payload.get("user_id"),
        strategy_id=strategy.id if strategy else None,
        strategy_version=strategy.version if strategy else None,
        strategy_snapshot_json=strategy_snapshot,
        selection_explanation_json=selection_explanation,
        selection_preview_id=payload.get("selection_preview_id"),
        selection_preview_request_hash=payload.get("selection_preview_request_hash"),
        fallback_trace_json={},
```

After `model_config = resolve_image_model_for_capability(...)`, update selected model in explanation:

```python
    if selection_explanation is not None:
        selection_explanation["selected_model_id"] = model_config.get("model_id")
        selection_explanation["resolved_scene_key"] = scene_key
        selection_explanation["resolved_capability_key"] = capability_key
```

Add strategy payload fields to `task_payload`:

```python
        "strategy": {
            "id": task.strategy_id,
            "version": task.strategy_version,
            "snapshot": task.strategy_snapshot_json or {},
        } if task.strategy_id else None,
        "selection_explanation": task.selection_explanation_json or {},
```

- [ ] **Step 6: Run snapshot and existing mocked E2E tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_strategy_snapshot.py tests/test_image_creation_mocked_e2e.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit task snapshot work**

```powershell
git add server/app/routers/image_creation.py server/app/services/image_creation_service.py server/tests/test_image_creation_strategy_snapshot.py server/tests/test_image_creation_mocked_e2e.py
git commit -m "feat: persist image strategy snapshots"
```

---

### Task 5: Add Approved Image Asset To Video Asset Bridge

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\app\services\image_asset_bridge_service.py`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\server\app\routers\image_production.py`
- Create: `D:\devWorkspace\jsProjects\dy_auto\server\tests\test_image_asset_bridge.py`

- [ ] **Step 1: Write failing bridge tests**

Create `server/tests/test_image_asset_bridge.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, ImageCreationAsset, ImageCreationTask, Series, VideoProductionAsset, VideoProductionRun
from app.main import app


client = TestClient(app)


def _run(db):
    series = Series(title="Bridge Series", description="")
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, title="Bridge Episode", episode_number=1, status="draft")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="image_review_pending", current_stage="image_review")
    db.add(run)
    db.commit()
    return run, episode


def _asset(db, status):
    task = ImageCreationTask(
        mode="text_to_image",
        output_mode="single",
        capability_key="text_to_image",
        prompt="bridge",
        status="completed",
        count=1,
        target_count=1,
        completed_count=1,
    )
    db.add(task)
    db.flush()
    asset = ImageCreationAsset(
        task_id=task.id,
        asset_type="image",
        asset_kind="image",
        url="http://127.0.0.1:8000/static/image-creation/bridge.png",
        status=status,
        version=1,
        slot_key=f"slot-{status}",
        destination_role="image_to_video_input",
        audit_status=status,
        manual_review_status=status,
        storage_status="persisted",
    )
    db.add(asset)
    db.commit()
    return asset


def test_approved_image_asset_promotes_to_video_asset(db):
    run, episode = _run(db)
    asset = _asset(db, "approved")

    resp = client.post(f"/api/image-production/assets/{asset.id}/promote-to-video-asset", json={
        "run_id": run.id,
        "episode_id": episode.id,
        "frame_id": "frame-001",
    })

    assert resp.status_code == 200
    video_asset = db.query(VideoProductionAsset).one()
    assert video_asset.run_id == run.id
    assert video_asset.frame_id == "frame-001"
    assert video_asset.status == "approved"
    assert video_asset.metadata_json["source_image_asset_id"] == asset.id
    db.refresh(asset)
    assert asset.downstream_usage_json[0]["video_asset_id"] == video_asset.id


def test_pending_image_asset_is_blocked_from_video_bridge(db):
    run, episode = _run(db)
    asset = _asset(db, "review_pending")

    resp = client.post(f"/api/image-production/assets/{asset.id}/promote-to-video-asset", json={
        "run_id": run.id,
        "episode_id": episode.id,
        "frame_id": "frame-001",
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "IMAGE_REVIEW_GATE_BLOCKED"
```

- [ ] **Step 2: Run bridge tests to verify they fail**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_asset_bridge.py -v
```

Expected: FAIL because bridge service and endpoint are missing.

- [ ] **Step 3: Implement bridge service**

Create `server/app/services/image_asset_bridge_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import ImageCreationAsset, VideoProductionAsset, VideoProductionRun
from app.services.image_creation_errors import image_error


def promote_image_asset_to_video_asset(db: Session, asset_id: str, payload: dict[str, Any]) -> VideoProductionAsset:
    asset = db.query(ImageCreationAsset).filter(ImageCreationAsset.id == asset_id).first()
    if not asset:
        raise image_error(404, "SOURCE_ASSET_NOT_FOUND", "Image asset was not found.", "Choose another asset.", retryable=False)
    if asset.status != "approved":
        raise image_error(409, "IMAGE_REVIEW_GATE_BLOCKED", "Image asset is not approved.", "Approve the asset before using it for video.", retryable=False, affected_ids=[asset.id])
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == payload["run_id"]).first()
    if not run:
        raise image_error(404, "VIDEO_RUN_NOT_FOUND", "Video production run was not found.", "Choose another run.", retryable=False)

    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.frame_id == payload["frame_id"],
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.version == int(payload.get("version") or 1),
    ).first()
    if existing:
        return existing

    video_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=payload.get("episode_id") or run.episode_id,
        frame_id=payload["frame_id"],
        asset_type="image",
        stage="image_review",
        url=asset.url,
        local_path=asset.local_path,
        thumbnail_url=asset.thumbnail_url,
        version=int(payload.get("version") or 1),
        metadata_json={
            "source_image_asset_id": asset.id,
            "source_image_task_id": asset.task_id,
            "source_image_version": asset.version,
            "destination_role": asset.destination_role,
            "review_snapshot": {
                "status": asset.status,
                "audit_status": asset.audit_status,
                "manual_review_status": asset.manual_review_status,
            },
        },
        status="approved",
        pixelle_task_id=asset.pixelle_task_id,
        provider_task_id=asset.provider_task_id,
        prompt_hash=asset.prompt_hash,
        source_version=asset.version,
        checksum=asset.checksum,
        size_bytes=asset.size_bytes,
    )
    db.add(video_asset)
    db.flush()
    usage = list(asset.downstream_usage_json or [])
    usage.append({
        "type": "video_asset",
        "video_asset_id": video_asset.id,
        "run_id": run.id,
        "frame_id": payload["frame_id"],
        "created_at": bj_now().isoformat(),
    })
    asset.downstream_usage_json = usage
    asset.updated_at = bj_now()
    db.commit()
    db.refresh(video_asset)
    return video_asset
```

- [ ] **Step 4: Add the bridge route**

Modify `server/app/routers/image_production.py`:

```python
from app.services.image_asset_bridge_service import promote_image_asset_to_video_asset


class PromoteImageAssetRequest(BaseModel):
    run_id: str
    episode_id: str | None = None
    frame_id: str
    version: int = 1


@router.post("/assets/{asset_id}/promote-to-video-asset")
def promote_asset(asset_id: str, body: PromoteImageAssetRequest, db: Session = Depends(get_db), _=Depends(verify_admin_token)):
    asset = promote_image_asset_to_video_asset(db, asset_id, body.model_dump())
    return {
        "ok": True,
        "video_asset": {
            "id": asset.id,
            "run_id": asset.run_id,
            "episode_id": asset.episode_id,
            "frame_id": asset.frame_id,
            "asset_type": asset.asset_type,
            "status": asset.status,
            "url": asset.url,
            "metadata": asset.metadata_json or {},
        },
    }
```

- [ ] **Step 5: Run bridge tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_asset_bridge.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit bridge**

```powershell
git add server/app/services/image_asset_bridge_service.py server/app/routers/image_production.py server/tests/test_image_asset_bridge.py
git commit -m "feat: bridge approved image assets to video assets"
```

---

### Task 6: Add Frontend API And Image Creation Trust Rail

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\api\imageProduction.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageCreationPage.vue`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-page.test.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-creation-a11y.test.js`

- [ ] **Step 1: Write failing frontend tests for strategy selector and preview**

Extend `web/src/__tests__/image-creation-page.test.js` with:

```javascript
it('shows image production strategy controls and sends strategy snapshot fields', async () => {
  const { mount } = await import('@vue/test-utils')
  const Page = (await import('../views/ImageCreationPage.vue')).default
  const imageProduction = await import('../api/imageProduction.js')
  const imageCreation = await import('../api/imageCreation.js')

  vi.spyOn(imageProduction, 'listImageProductionStrategies').mockResolvedValue({
    data: {
      strategies: [{
        id: 'strategy-1',
        name: '默认分镜首帧',
        destination_role: 'storyboard_first_frame',
        supported_modes: ['text_to_image'],
        version: 2,
        status: 'active',
      }],
    },
  })
  vi.spyOn(imageProduction, 'previewImageSelection').mockResolvedValue({
    data: {
      selected_model: { model_id: 'model-1', name: 'Mock Image' },
      selection_explanation: { selected_reason: 'strategy_default_model', rejected_candidates: [] },
      cost_estimate: { amount: 1, currency: 'CNY' },
      selection_preview_id: 'preview-1',
      request_hash: 'hash-1',
    },
  })
  vi.spyOn(imageCreation, 'createImageTask').mockResolvedValue({ data: { task: { id: 'task-1' }, assets: [] } })

  const wrapper = mount(Page)
  await Promise.resolve()

  await wrapper.find('[data-testid="destination-role"]').setValue('storyboard_first_frame')
  await wrapper.find('[data-testid="image-prompt"]').setValue('first frame')
  await wrapper.find('[data-testid="strategy-select"]').setValue('strategy-1')
  await wrapper.find('[data-testid="selection-preview-button"]').trigger('click')
  await Promise.resolve()

  expect(wrapper.text()).toContain('模型选择理由')
  expect(wrapper.text()).toContain('Mock Image')

  await wrapper.find('[data-testid="image-create-submit"]').trigger('click')
  expect(imageCreation.createImageTask).toHaveBeenCalledWith(expect.objectContaining({
    strategy_id: 'strategy-1',
    strategy_version: 2,
    selection_preview_id: 'preview-1',
    selection_preview_request_hash: 'hash-1',
  }))
})
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run test -- --run src/__tests__/image-creation-page.test.js
```

Expected: FAIL because `imageProduction.js`, `strategy-select`, and preview controls do not exist.

- [ ] **Step 3: Add frontend API wrapper**

Create `web/src/api/imageProduction.js`:

```javascript
import client from './client.js'

export function listImageProductionStrategies(params = {}) {
  return client.get('/image-production/strategies', { params })
}

export function createImageProductionStrategy(payload) {
  return client.post('/image-production/strategies', payload)
}

export function updateImageProductionStrategy(strategyId, payload) {
  return client.put(`/image-production/strategies/${strategyId}`, payload)
}

export function archiveImageProductionStrategy(strategyId) {
  return client.post(`/image-production/strategies/${strategyId}/archive`)
}

export function activateImageProductionStrategy(strategyId) {
  return client.post(`/image-production/strategies/${strategyId}/activate`)
}

export function previewImageSelection(payload) {
  return client.post('/image-production/selection-preview', payload)
}

export function promoteImageAssetToVideo(assetId, payload) {
  return client.post(`/image-production/assets/${assetId}/promote-to-video-asset`, payload)
}
```

- [ ] **Step 4: Add state and preview functions to ImageCreationPage**

Modify the `<script setup>` section in `web/src/views/ImageCreationPage.vue`:

```javascript
import {
  listImageProductionStrategies,
  previewImageSelection,
} from '../api/imageProduction.js'

const strategies = ref([])
const selectedStrategyId = ref('')
const selectionPreview = ref(null)
const previewLoading = ref(false)
const previewError = ref('')

const selectedStrategy = computed(() =>
  strategies.value.find((strategy) => strategy.id === selectedStrategyId.value) || null
)

async function loadStrategies() {
  const resp = await listImageProductionStrategies({ status: 'active' })
  strategies.value = resp.data.strategies || []
}

async function runSelectionPreview() {
  previewError.value = ''
  previewLoading.value = true
  try {
    const resp = await previewImageSelection({
      mode: form.mode,
      destination_role: form.destination_role || selectedStrategy.value?.destination_role || '',
      strategy_id: selectedStrategy.value?.id || null,
      strategy_version: selectedStrategy.value?.version || null,
      model_id: form.modelId || null,
      count: form.count,
      provider_options: form.providerOptions,
      output_format: form.output_format || null,
    })
    selectionPreview.value = resp.data
  } catch (err) {
    previewError.value = err.response?.data?.detail?.user_message || '选择预览失败'
  } finally {
    previewLoading.value = false
  }
}
```

Ensure `onMounted` calls `loadStrategies()`.

When building submit payload, add:

```javascript
strategy_id: selectedStrategy.value?.id || null,
strategy_version: selectedStrategy.value?.version || null,
selection_preview_id: selectionPreview.value?.selection_preview_id || null,
selection_preview_request_hash: selectionPreview.value?.request_hash || null,
```

- [ ] **Step 5: Add strategy selector and trust rail markup**

Add this near the destination role section:

```html
<div>
  <label class="mb-2 block text-sm font-medium text-slate-300" for="strategy-select">生产策略</label>
  <select
    id="strategy-select"
    v-model="selectedStrategyId"
    data-testid="strategy-select"
    class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
  >
    <option value="">自动策略</option>
    <option v-for="strategy in strategies" :key="strategy.id" :value="strategy.id">
      {{ strategy.name }} v{{ strategy.version }}
    </option>
  </select>
</div>
```

Add trust rail markup in the right column:

```html
<aside data-testid="image-trust-rail" class="space-y-4 border border-slate-800 bg-slate-950/70 p-5">
  <div class="flex items-center justify-between gap-3">
    <h2 class="text-base font-semibold">生产信任检查</h2>
    <button
      type="button"
      data-testid="selection-preview-button"
      class="border border-sky-500/40 px-3 py-2 text-sm text-sky-200 hover:bg-sky-950/50 disabled:opacity-50"
      :disabled="previewLoading || !form.mode"
      @click="runSelectionPreview"
    >
      {{ previewLoading ? '预览中...' : '选择预览' }}
    </button>
  </div>
  <p v-if="previewError" class="text-sm text-rose-300">{{ previewError }}</p>
  <div v-if="selectionPreview" class="space-y-3 text-sm">
    <div>
      <p class="text-slate-400">模型选择理由</p>
      <p class="mt-1 text-slate-100">{{ selectionPreview.selected_model?.name || selectionPreview.selected_model?.model_id }}</p>
      <p class="mt-1 text-xs text-slate-500">{{ selectionPreview.selection_explanation?.selected_reason }}</p>
    </div>
    <div>
      <p class="text-slate-400">预计成本</p>
      <p class="mt-1 text-slate-100">
        {{ selectionPreview.cost_estimate?.amount }} {{ selectionPreview.cost_estimate?.currency }}
      </p>
    </div>
    <details class="border-t border-slate-800 pt-3">
      <summary class="cursor-pointer text-slate-300">审计详情</summary>
      <pre class="mt-3 max-h-64 overflow-auto bg-slate-900 p-3 text-xs text-slate-300">{{ JSON.stringify(selectionPreview.selection_explanation, null, 2) }}</pre>
    </details>
  </div>
  <p v-else class="text-sm text-slate-500">提交前先运行选择预览，确认模型、成本和审查门禁。</p>
</aside>
```

- [ ] **Step 6: Run frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run test -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js
```

Expected: PASS.

- [ ] **Step 7: Commit image creation UI**

```powershell
git add web/src/api/imageProduction.js web/src/views/ImageCreationPage.vue web/src/__tests__/image-creation-page.test.js web/src/__tests__/image-creation-a11y.test.js
git commit -m "feat: add image creation strategy trust rail"
```

---

### Task 7: Add Strategy Center Page

**Files:**
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\views\ImageProductionStrategiesPage.vue`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\router\index.js`
- Modify: `D:\devWorkspace\jsProjects\dy_auto\web\src\constants\navigation.js`
- Create: `D:\devWorkspace\jsProjects\dy_auto\web\src\__tests__\image-production-strategy-page.test.js`

- [ ] **Step 1: Write failing strategy page tests**

Create `web/src/__tests__/image-production-strategy-page.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import Page from '../views/ImageProductionStrategiesPage.vue'
import * as api from '../api/imageProduction.js'


describe('ImageProductionStrategiesPage', () => {
  it('renders strategy table and archive action', async () => {
    vi.spyOn(api, 'listImageProductionStrategies').mockResolvedValue({
      data: {
        strategies: [{
          id: 'strategy-1',
          name: '默认图生视频输入图',
          destination_role: 'image_to_video_input',
          status: 'active',
          version: 1,
          default_model_id: null,
          fallback_model_ids: [],
        }],
      },
    })
    vi.spyOn(api, 'archiveImageProductionStrategy').mockResolvedValue({ data: { ok: true } })

    const wrapper = mount(Page)
    await Promise.resolve()

    expect(wrapper.text()).toContain('图像策略中心')
    expect(wrapper.text()).toContain('默认图生视频输入图')
    await wrapper.find('[data-testid="archive-strategy-strategy-1"]').trigger('click')
    expect(api.archiveImageProductionStrategy).toHaveBeenCalledWith('strategy-1')
  })
})
```

- [ ] **Step 2: Run strategy page test to verify it fails**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run test -- --run src/__tests__/image-production-strategy-page.test.js
```

Expected: FAIL because the page does not exist.

- [ ] **Step 3: Implement the strategy center page**

Create `web/src/views/ImageProductionStrategiesPage.vue`:

```vue
<template>
  <div class="min-h-full bg-slate-950 px-4 py-6 text-slate-100 sm:px-6">
    <div class="mx-auto max-w-7xl">
      <header class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold">图像策略中心</h1>
          <p class="mt-1 text-sm text-slate-400">管理图像生产策略、版本和审查入口。</p>
        </div>
        <button
          type="button"
          class="border border-emerald-500/40 bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          @click="seedDefaults"
        >
          导入默认策略
        </button>
      </header>

      <section class="border border-slate-800 bg-slate-950/70">
        <div class="grid grid-cols-[minmax(220px,1fr)_160px_120px_100px_180px] border-b border-slate-800 px-4 py-3 text-xs font-semibold text-slate-400">
          <span>策略</span>
          <span>用途</span>
          <span>状态</span>
          <span>版本</span>
          <span>操作</span>
        </div>
        <div v-if="loading" class="px-4 py-8 text-sm text-slate-400">加载中...</div>
        <div v-else-if="strategies.length === 0" class="px-4 py-8 text-sm text-slate-400">暂无策略，可导入默认策略。</div>
        <div
          v-for="strategy in strategies"
          :key="strategy.id"
          class="grid grid-cols-[minmax(220px,1fr)_160px_120px_100px_180px] items-center border-b border-slate-900 px-4 py-3 text-sm"
        >
          <div>
            <p class="font-medium text-slate-100">{{ strategy.name }}</p>
            <p class="mt-1 text-xs text-slate-500">{{ strategy.id }}</p>
          </div>
          <span class="text-slate-300">{{ roleLabel(strategy.destination_role) }}</span>
          <span class="w-fit border px-2 py-1 text-xs" :class="strategy.status === 'active' ? 'border-emerald-500/40 text-emerald-300' : 'border-slate-700 text-slate-400'">
            {{ strategy.status }}
          </span>
          <span>v{{ strategy.version }}</span>
          <button
            type="button"
            :data-testid="`archive-strategy-${strategy.id}`"
            class="w-fit border border-amber-500/40 px-3 py-2 text-xs text-amber-200 hover:bg-amber-950/40"
            @click="archive(strategy.id)"
          >
            归档
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  archiveImageProductionStrategy,
  listImageProductionStrategies,
} from '../api/imageProduction.js'

const strategies = ref([])
const loading = ref(false)

const roleLabels = {
  character_anchor_image: '角色锚定图',
  storyboard_first_frame: '分镜首帧',
  image_to_video_input: '图生视频输入图',
}

function roleLabel(role) {
  return roleLabels[role] || role || '未指定'
}

async function loadStrategies() {
  loading.value = true
  try {
    const resp = await listImageProductionStrategies({})
    strategies.value = resp.data.strategies || []
  } finally {
    loading.value = false
  }
}

async function seedDefaults() {
  await loadStrategies()
}

async function archive(id) {
  await archiveImageProductionStrategy(id)
  await loadStrategies()
}

onMounted(loadStrategies)
</script>
```

- [ ] **Step 4: Add route and navigation item**

Modify `web/src/router/index.js` after the `image-creation` route:

```javascript
{
  path: 'image-production/strategies',
  name: 'ImageProductionStrategies',
  component: () => import('../views/ImageProductionStrategiesPage.vue'),
},
```

Modify `web/src/constants/navigation.js` in the AI 视频 section:

```javascript
{ name: '图像策略中心', path: '/image-production/strategies', icon: 'M9 17v-2a4 4 0 014-4h6M9 7h12M3 7h2m-2 5h2m-2 5h2m4-5h12' },
```

Add route category mapping:

```javascript
'/image-production/strategies': 'ai-video',
```

Use the existing mapping style in the file rather than adding a new helper.

- [ ] **Step 5: Run strategy page tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run test -- --run src/__tests__/image-production-strategy-page.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit strategy center UI**

```powershell
git add web/src/views/ImageProductionStrategiesPage.vue web/src/router/index.js web/src/constants/navigation.js web/src/__tests__/image-production-strategy-page.test.js
git commit -m "feat: add image production strategy center"
```

---

### Task 8: Full Regression Pass And Documentation Sync

**Files:**
- Modify: `D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\plans\2026-05-28-image-production-strategy-control-plane-phase1.md` only if execution notes reveal command changes.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_production_migration.py tests/test_image_production_strategy_service.py tests/test_image_selection_preview_service.py tests/test_image_creation_strategy_snapshot.py tests/test_image_asset_bridge.py tests/test_image_creation_mocked_e2e.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend broader image tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
python -m pytest tests/test_image_creation_api.py tests/test_image_creation_models.py tests/test_image_creation_model_resolution.py tests/test_image_creation_pixelle_client.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend focused tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run test -- --run src/__tests__/image-creation-page.test.js src/__tests__/image-creation-a11y.test.js src/__tests__/image-production-strategy-page.test.js src/__tests__/image-creation-api.test.js src/__tests__/navigation.test.js
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npm run build
```

Expected: PASS. Existing chunk-size warnings are acceptable if there are no new errors.

- [ ] **Step 5: Confirm no generated secrets are exposed**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
rg -n "ark-[0-9a-f-]+|secret-key|api_key.+selection|api_key.+snapshot" server/app server/tests web/src
```

Expected: only test fixture strings appear; no production response code exposes decrypted API keys.

- [ ] **Step 6: Commit final regression notes if needed**

If test commands required plan command corrections, update this plan and commit:

```powershell
git add docs/superpowers/plans/2026-05-28-image-production-strategy-control-plane-phase1.md
git commit -m "docs: update image production phase 1 test commands"
```

If no corrections are needed, do not create an empty commit.

---

## Phase 1 Completion Criteria

- Backend supports strategy CRUD with immutable version snapshots.
- Default strategy seeds are idempotent.
- Selection preview explains selected and rejected models from `AIModel.config_json`.
- Existing image task creation works without a strategy.
- Strategy-backed image task creation persists strategy and selection snapshots before Pixelle submission.
- Image creation APIs require the existing admin token boundary.
- Approved image assets can be promoted to `VideoProductionAsset`.
- Unapproved image assets are blocked by `IMAGE_REVIEW_GATE_BLOCKED`.
- Image creation UI shows strategy, trust rail, preview result, cost estimate, and audit details.
- Strategy center page lists and archives strategies.
- All focused backend tests pass.
- All focused frontend tests pass.
- Frontend build passes.

## Self-Review

Spec coverage:

- Strategy center MVP is covered by Tasks 1, 2, and 7.
- Explainable selection MVP is covered by Task 3 and the trust rail in Task 6.
- Task snapshot and reproducibility are covered by Task 4.
- Review gate and bridge are covered by Task 5.
- Security and auth are covered by Task 4.
- Migration and default seeds are covered by Tasks 1 and 2.
- Testing and regression are covered by Tasks 1 through 8.

Deferred scope:

- A/B groups and attempts are explicitly outside Phase 1.
- Full capacity leasing is explicitly outside Phase 1.
- Automatic strategy mutation is explicitly outside Phase 1.

Placeholder scan:

- No unspecified file paths are used.
- No step relies on an unnamed test file.
- No task asks an engineer to write generic validation without showing the intended behavior.
- All execution commands include expected results.

Type consistency:

- Backend strategy fields use `strategy_id`, `strategy_version`, `strategy_snapshot_json`, `selection_explanation_json`, `selection_preview_id`, and `selection_preview_request_hash` consistently across schema, service, route, and frontend payload.
- Frontend strategy API names match the planned `web/src/api/imageProduction.js` exports.
- Bridge payload fields are `run_id`, `episode_id`, `frame_id`, and `version`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-28-image-production-strategy-control-plane-phase1.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
