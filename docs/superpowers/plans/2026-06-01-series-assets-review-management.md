# Series Assets Review Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the management loop for series, character assets, scene assets, reference images, and review-center image edits without breaking one-click video production.

**Architecture:** Keep existing tables and routes where possible. Add focused backend services for lifecycle guards, reference image generation, AI rewrite candidates, and review image editing; routes only validate input and call services. Frontend adds reusable drawers/dialogs/galleries and wires them into existing pages instead of creating a new asset system.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Vitest, existing `client` API wrapper, existing AI model registry/runtime model config services.

---

## Source Spec

Implement from:

- `docs/superpowers/specs/2026-06-01-series-assets-review-management-design.md`

Hard boundaries from the spec:

- Do not build a visual timeline editor.
- Do not add a separate media library product.
- Do not physically delete production assets from the review center.
- Do not bypass image, video, or final review gates.
- Do not duplicate provider calls in route files.
- Keep all new frontend visible labels in Chinese.

## File Structure

### Backend Files

- Create `server/app/services/asset_lifecycle_service.py`
  - Owns series archive vs hard delete decisions.
  - Owns character/scene hard delete vs archive decisions.
  - Detects references from series links, `story_bible_json`, `storyboard_json`, production runs, production assets, generated videos, and pipeline runs.

- Create `server/app/services/reference_asset_service.py`
  - Owns role/scene reference image slot validation.
  - Resolves model config for `image_generation`.
  - Calls existing image provider path through one service.
  - Updates character/scene URL fields and `meta_json.reference_generation`.

- Create `server/app/services/asset_ai_rewrite_service.py`
  - Owns AI rewrite candidate generation for character and scene records.
  - Returns candidates only. It must not persist changes.

- Create `server/app/services/review_asset_edit_service.py`
  - Owns image review edit/redraw.
  - Creates a new `VideoProductionAsset` version linked to the same run, episode, frame, and source asset.
  - Marks older latest asset versions as `is_latest=False` only after the new asset is created.

- Modify `server/app/routers/series.py`
  - Add `PUT /api/series/{series_id}`.
  - Add unlink endpoints for series characters/scenes.
  - Use `asset_lifecycle_service` for safe delete/archive.

- Modify `server/app/routers/characters.py`
  - Use lifecycle service for delete/archive.
  - Add AI rewrite endpoint.
  - Add reference image generation endpoint.
  - Return `meta_json.archived` records only when explicitly requested.

- Modify `server/app/routers/scenes.py`
  - Same pattern as characters for delete/archive, AI rewrite, and reference generation.

- Modify `server/app/routers/video_production.py`
  - Add `POST /api/video-production/assets/{asset_id}/void`.
  - Add `POST /api/video-production/assets/{asset_id}/image-edit`.
  - Include `reference_evidence` in review-item payloads.

- Test files:
  - Create `server/tests/test_asset_lifecycle_service.py`
  - Create `server/tests/test_reference_asset_service.py`
  - Create `server/tests/test_asset_ai_rewrite_service.py`
  - Create `server/tests/test_review_asset_edit_service.py`
  - Create `server/tests/test_asset_archive_api.py`
  - Modify `server/tests/test_series_api.py`
  - Modify `server/tests/test_video_production_api.py`

### Frontend Files

- Create `web/src/components/assets/AssetDetailDrawer.vue`
  - Shared drawer shell for character/scene details.
  - Must reuse the existing dark admin vocabulary from `PageContainer.vue`, `AppDialog.vue`, `AppButton.vue`, `EmptyState.vue`, and `StatusBadge.vue` instead of inventing a second visual system.

- Create `web/src/components/assets/ReferenceImageGallery.vue`
  - Shared reference image gallery with preview, copy, URL replace, and regenerate actions.
  - Must use visible labels for every URL input. Placeholder text is helper text only, never the only label.

- Create `web/src/components/assets/AiRewriteConfirmDialog.vue`
  - Shows AI rewrite candidates before saving.
  - Must present candidate changes as a before/after review surface, not as a blind overwrite form.

- Create `web/src/components/assets/DangerConfirmDialog.vue`
  - Shared Chinese confirmation dialog for delete/archive/void actions.
  - Prefer composing the existing `AppDialog.vue` and `AppButton.vue`; create this wrapper only to standardize Chinese destructive-copy and impact summaries.

- Modify `web/src/api/series.js`
  - Add series update and unlink APIs.

- Modify `web/src/api/characters.js`
  - Add or extend delete, AI rewrite, and reference generation APIs.

- Modify `web/src/api/scenes.js`
  - Add or extend delete, AI rewrite, and reference generation APIs.

- Modify `web/src/api/videoProduction.js`
  - Add void and image-edit APIs.

- Modify `web/src/views/CharactersPage.vue`
  - Add drawer, edit, archive/delete, AI rewrite, reference gallery.

- Modify `web/src/views/ScenesPage.vue`
  - Add drawer, edit, archive/delete, AI rewrite, reference gallery.

- Modify `web/src/views/SeriesDetailPage.vue`
  - Add series settings edit, safe delete/archive, linked character/scene management, reference image entry.

- Modify `web/src/views/AIVideoReviewPage.vue`
  - Add reference evidence section, image edit/redraw dialog, void current version action.

- Test files:
  - Create `web/src/__tests__/asset-detail-drawer.test.js`
  - Create `web/src/__tests__/reference-image-gallery.test.js`
  - Create `web/src/__tests__/characters-management-page.test.js`
  - Create `web/src/__tests__/scenes-management-page.test.js`
  - Modify `web/src/__tests__/series-detail-video-production.test.js`
  - Modify `web/src/__tests__/ai-video-review-page.test.js`

---

## Task 1: Backend Lifecycle Guards And Series Management

**Files:**

- Create: `server/app/services/asset_lifecycle_service.py`
- Modify: `server/app/routers/series.py`
- Modify: `server/app/routers/characters.py`
- Modify: `server/app/routers/scenes.py`
- Test: `server/tests/test_asset_lifecycle_service.py`
- Test: `server/tests/test_series_api.py`
- Test: `server/tests/test_asset_archive_api.py`

- [ ] **Step 1: Write failing lifecycle service tests**

Create `server/tests/test_asset_lifecycle_service.py`:

```python
from app.db_models import (
    Character,
    Episode,
    GeneratedVideo,
    PipelineRun,
    Scene,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
)
from app.services.asset_lifecycle_service import (
    AssetLifecycleError,
    archive_character_or_scene,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)


def create_series(db, title="Series"):
    series = Series(title=title, logline="Story", genre="drama", total_episodes=1, target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    return series, episode


def test_series_without_production_history_is_hard_deleted(db):
    series, _ = create_series(db)
    db.commit()

    result = delete_or_archive_series(db, series.id)

    assert result["action"] == "deleted"
    assert db.query(Series).filter(Series.id == series.id).first() is None


def test_series_with_video_run_is_archived_not_deleted(db):
    series, episode = create_series(db)
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status="completed", current_stage="final")
    db.add(run)
    db.commit()

    result = delete_or_archive_series(db, series.id)

    saved = db.query(Series).filter(Series.id == series.id).one()
    assert result["action"] == "archived"
    assert saved.status == "archived"


def test_series_with_generated_video_is_archived_not_deleted(db):
    series, episode = create_series(db)
    video = GeneratedVideo(
        task_id="task-1",
        title="Generated",
        video_path="/tmp/final.mp4",
        status="completed",
        pixelle_task_id="task-1",
    )
    episode.video_url = "/media/final.mp4"
    db.add(video)
    db.commit()

    result = delete_or_archive_series(db, series.id)

    saved = db.query(Series).filter(Series.id == series.id).one()
    assert result["action"] == "archived"
    assert saved.status == "archived"


def test_unlink_character_from_series(db):
    series, _ = create_series(db)
    character = Character(name="Lin", role_type="protagonist", gender="female")
    series.characters.append(character)
    db.add(character)
    db.commit()

    result = unlink_character_from_series(db, series.id, character.id)

    assert result["ok"] is True
    db.refresh(series)
    assert character not in series.characters


def test_unlink_scene_from_series(db):
    series, _ = create_series(db)
    scene = Scene(name="Office", scene_type="indoor")
    series.scenes.append(scene)
    db.add(scene)
    db.commit()

    result = unlink_scene_from_series(db, series.id, scene.id)

    assert result["ok"] is True
    db.refresh(series)
    assert scene not in series.scenes


def test_referenced_character_is_archived_not_hard_deleted(db):
    series, episode = create_series(db)
    character = Character(name="Lin", role_type="protagonist", gender="female")
    series.characters.append(character)
    episode.storyboard_json = {"frames": [{"character_ids": [character.id]}]}
    db.add(character)
    db.commit()

    result = archive_character_or_scene(db, "character", character.id)

    saved = db.query(Character).filter(Character.id == character.id).one()
    assert result["action"] == "archived"
    assert saved.meta_json["archived"] is True


def test_unreferenced_character_is_hard_deleted(db):
    character = Character(name="Temp", role_type="cameo", gender="male")
    db.add(character)
    db.commit()

    result = archive_character_or_scene(db, "character", character.id)

    assert result["action"] == "deleted"
    assert db.query(Character).filter(Character.id == character.id).first() is None


def test_referenced_scene_is_archived_not_hard_deleted(db):
    series, episode = create_series(db)
    scene = Scene(name="Market", scene_type="outdoor")
    series.scenes.append(scene)
    episode.storyboard_json = {"frames": [{"scene_id": scene.id}]}
    db.add(scene)
    db.commit()

    result = archive_character_or_scene(db, "scene", scene.id)

    saved = db.query(Scene).filter(Scene.id == scene.id).one()
    assert result["action"] == "archived"
    assert saved.meta_json["archived"] is True


def test_unknown_asset_type_raises(db):
    try:
        archive_character_or_scene(db, "prop", "missing")
    except AssetLifecycleError as exc:
        assert exc.code == "ASSET_TYPE_UNSUPPORTED"
    else:
        raise AssertionError("expected AssetLifecycleError")
```

- [ ] **Step 2: Run lifecycle tests to verify they fail**

Run:

```powershell
pytest server/tests/test_asset_lifecycle_service.py -q
```

Expected:

- FAIL because `app.services.asset_lifecycle_service` does not exist.

- [ ] **Step 3: Implement lifecycle service**

Create `server/app/services/asset_lifecycle_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import (
    Character,
    Episode,
    GeneratedVideo,
    PipelineRun,
    Scene,
    Series,
    VideoProductionAsset,
    VideoProductionRun,
    series_characters,
    series_scenes,
)


@dataclass
class AssetLifecycleError(ValueError):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def _json_contains_id(value: Any, target_id: str) -> bool:
    if isinstance(value, dict):
        return any(_json_contains_id(item, target_id) for item in value.values())
    if isinstance(value, list):
        return any(_json_contains_id(item, target_id) for item in value)
    return value == target_id


def _series_production_dependencies(db: Session, series_id: str) -> list[str]:
    deps: list[str] = []
    if db.query(VideoProductionRun).filter(VideoProductionRun.series_id == series_id).first():
        deps.append("video_production_runs")
    if db.query(PipelineRun).filter(PipelineRun.series_id == series_id).first():
        deps.append("pipeline_runs")
    if db.query(Episode).filter(Episode.series_id == series_id, Episode.video_url.isnot(None)).first():
        deps.append("episode_video_url")
    episode_ids = [row[0] for row in db.query(Episode.id).filter(Episode.series_id == series_id).all()]
    if episode_ids and db.query(VideoProductionAsset).filter(VideoProductionAsset.episode_id.in_(episode_ids)).first():
        deps.append("video_production_assets")
    return deps


def delete_or_archive_series(db: Session, series_id: str) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise AssetLifecycleError("SERIES_NOT_FOUND", "Series not found")

    dependencies = _series_production_dependencies(db, series_id)
    if dependencies:
        series.status = "archived"
        series.updated_at = bj_now()
        db.commit()
        db.refresh(series)
        return {"ok": True, "action": "archived", "series_id": series_id, "dependencies": dependencies}

    db.execute(series_characters.delete().where(series_characters.c.series_id == series_id))
    db.execute(series_scenes.delete().where(series_scenes.c.series_id == series_id))
    db.query(Episode).filter(Episode.series_id == series_id).delete()
    db.delete(series)
    db.commit()
    return {"ok": True, "action": "deleted", "series_id": series_id, "dependencies": []}


def unlink_character_from_series(db: Session, series_id: str, character_id: str) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    character = db.query(Character).filter(Character.id == character_id).first()
    if not series or not character:
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Series or character not found")
    if character in series.characters:
        series.characters.remove(character)
    db.commit()
    return {"ok": True, "series_id": series_id, "character_id": character_id}


def unlink_scene_from_series(db: Session, series_id: str, scene_id: str) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not series or not scene:
        raise AssetLifecycleError("ASSET_NOT_FOUND", "Series or scene not found")
    if scene in series.scenes:
        series.scenes.remove(scene)
    db.commit()
    return {"ok": True, "series_id": series_id, "scene_id": scene_id}


def _character_reference_dependencies(db: Session, character_id: str) -> list[str]:
    deps: list[str] = []
    if db.query(series_characters).filter(series_characters.c.character_id == character_id).first():
        deps.append("series_characters")
    for series in db.query(Series).all():
        if _json_contains_id(series.story_bible_json or {}, character_id):
            deps.append("series_story_bible")
            break
    for episode in db.query(Episode).all():
        if _json_contains_id(episode.storyboard_json or {}, character_id):
            deps.append("episode_storyboard")
            break
    for asset in db.query(VideoProductionAsset).all():
        if _json_contains_id(asset.metadata_json or {}, character_id):
            deps.append("video_production_asset")
            break
    return deps


def _scene_reference_dependencies(db: Session, scene_id: str) -> list[str]:
    deps: list[str] = []
    if db.query(series_scenes).filter(series_scenes.c.scene_id == scene_id).first():
        deps.append("series_scenes")
    for series in db.query(Series).all():
        if _json_contains_id(series.story_bible_json or {}, scene_id):
            deps.append("series_story_bible")
            break
    for episode in db.query(Episode).all():
        if _json_contains_id(episode.storyboard_json or {}, scene_id):
            deps.append("episode_storyboard")
            break
    for asset in db.query(VideoProductionAsset).all():
        if _json_contains_id(asset.metadata_json or {}, scene_id):
            deps.append("video_production_asset")
            break
    return deps


def _archive_row(row: Character | Scene) -> None:
    meta = dict(row.meta_json or {})
    meta["archived"] = True
    meta["archived_at"] = bj_now().isoformat()
    row.meta_json = meta
    row.updated_at = bj_now()


def archive_character_or_scene(db: Session, asset_type: str, asset_id: str) -> dict[str, Any]:
    if asset_type == "character":
        row = db.query(Character).filter(Character.id == asset_id).first()
        if not row:
            raise AssetLifecycleError("ASSET_NOT_FOUND", "Character not found")
        dependencies = _character_reference_dependencies(db, asset_id)
    elif asset_type == "scene":
        row = db.query(Scene).filter(Scene.id == asset_id).first()
        if not row:
            raise AssetLifecycleError("ASSET_NOT_FOUND", "Scene not found")
        dependencies = _scene_reference_dependencies(db, asset_id)
    else:
        raise AssetLifecycleError("ASSET_TYPE_UNSUPPORTED", f"Unsupported asset type: {asset_type}")

    if dependencies:
        _archive_row(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "action": "archived", "asset_type": asset_type, "asset_id": asset_id, "dependencies": dependencies}

    db.delete(row)
    db.commit()
    return {"ok": True, "action": "deleted", "asset_type": asset_type, "asset_id": asset_id, "dependencies": []}
```

- [ ] **Step 4: Run lifecycle tests to verify they pass**

Run:

```powershell
pytest server/tests/test_asset_lifecycle_service.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Write failing API tests for series edit, unlink, and safe delete**

Append these tests to `server/tests/test_series_api.py`:

```python
    def test_update_series_basic_fields(self, client):
        series_id = self._create_series(client).json()["series"]["id"]

        resp = client.put(f"/api/series/{series_id}", json={
            "title": "Updated Series",
            "logline": "Updated story",
            "genre": "comedy",
            "target_duration": 120,
            "mode": "fully_automatic",
            "pilot_first": False,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["series"]["title"] == "Updated Series"
        assert data["series"]["target_duration"] == 120
        assert data["series"]["pilot_first"] is False

    def test_unlink_character_from_series_api(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        char_id = client.post("/api/characters", json={
            "name": "男主", "role_type": "protagonist", "gender": "male",
        }).json()["character"]["id"]
        client.post(f"/api/series/{series_id}/characters/{char_id}")

        resp = client.delete(f"/api/series/{series_id}/characters/{char_id}")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_unlink_scene_from_series_api(self, client):
        series_id = self._create_series(client).json()["series"]["id"]
        scene_id = client.post("/api/scenes", json={
            "name": "办公室", "scene_type": "indoor",
        }).json()["scene"]["id"]
        client.post(f"/api/series/{series_id}/scenes/{scene_id}")

        resp = client.delete(f"/api/series/{series_id}/scenes/{scene_id}")

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_series_with_no_history_returns_deleted_action(self, client):
        series_id = self._create_series(client).json()["series"]["id"]

        resp = client.delete(f"/api/series/{series_id}")

        assert resp.status_code == 200
        assert resp.json()["action"] == "deleted"
```

Create `server/tests/test_asset_archive_api.py`:

```python
from app.db_models import Character, Scene


def test_characters_hide_archived_by_default(client, db):
    active = Character(name="Active", role_type="protagonist", gender="female")
    archived = Character(name="Archived", role_type="supporting", gender="male", meta_json={"archived": True})
    db.add_all([active, archived])
    db.commit()

    resp = client.get("/api/characters")

    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["characters"]}
    assert "Active" in names
    assert "Archived" not in names


def test_characters_can_include_archived(client, db):
    archived = Character(name="Archived", role_type="supporting", gender="male", meta_json={"archived": True})
    db.add(archived)
    db.commit()

    resp = client.get("/api/characters?include_archived=true")

    assert resp.status_code == 200
    assert any(item["name"] == "Archived" for item in resp.json()["characters"])


def test_scenes_hide_archived_by_default(client, db):
    active = Scene(name="Active Scene", scene_type="indoor")
    archived = Scene(name="Archived Scene", scene_type="outdoor", meta_json={"archived": True})
    db.add_all([active, archived])
    db.commit()

    resp = client.get("/api/scenes")

    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["scenes"]}
    assert "Active Scene" in names
    assert "Archived Scene" not in names


def test_scenes_can_include_archived(client, db):
    archived = Scene(name="Archived Scene", scene_type="outdoor", meta_json={"archived": True})
    db.add(archived)
    db.commit()

    resp = client.get("/api/scenes?include_archived=true")

    assert resp.status_code == 200
    assert any(item["name"] == "Archived Scene" for item in resp.json()["scenes"])
```

- [ ] **Step 6: Run API tests to verify new tests fail**

Run:

```powershell
pytest server/tests/test_series_api.py::TestSeriesAPI server/tests/test_asset_archive_api.py -q
```

Expected:

- FAIL because `PUT /api/series/{id}`, unlink `DELETE` endpoints, and `include_archived` filters are missing.

- [ ] **Step 7: Add series update and unlink routes**

Modify `server/app/routers/series.py`.

Add imports:

```python
from sqlalchemy.orm.attributes import flag_modified
from app.services.asset_lifecycle_service import (
    AssetLifecycleError,
    delete_or_archive_series,
    unlink_character_from_series,
    unlink_scene_from_series,
)
```

Add request model near `SeriesCreate`:

```python
class SeriesUpdate(BaseModel):
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    total_episodes: Optional[int] = None
    target_duration: Optional[int] = None
    mode: Optional[str] = None
    pilot_first: Optional[bool] = None
```

Add helper:

```python
def _lifecycle_http_error(exc: AssetLifecycleError) -> HTTPException:
    status = 404 if exc.code in {"SERIES_NOT_FOUND", "ASSET_NOT_FOUND"} else 409
    return HTTPException(status_code=status, detail={
        "code": exc.code,
        "message": exc.message,
        "details": exc.details or {},
    })
```

Add route before `@router.delete("/{series_id}")`:

```python
@router.put("/{series_id}")
def update_series(series_id: str, body: SeriesUpdate, db: Session = Depends(get_db),
                  user=Depends(verify_admin_token)):
    s = db.query(Series).filter(Series.id == series_id).first()
    if not s:
        raise HTTPException(404, "Series not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(s, key, value)
    db.commit()
    db.refresh(s)
    return {"ok": True, "series": _series_dict(s)}
```

Replace the existing `delete_series` body with:

```python
@router.delete("/{series_id}")
def delete_series(series_id: str, db: Session = Depends(get_db),
                  user=Depends(verify_admin_token)):
    try:
        result = delete_or_archive_series(db, series_id)
    except AssetLifecycleError as exc:
        raise _lifecycle_http_error(exc)
    return result
```

Add unlink routes before episode management:

```python
@router.delete("/{series_id}/characters/{character_id}")
def unlink_character(series_id: str, character_id: str, db: Session = Depends(get_db),
                     user=Depends(verify_admin_token)):
    try:
        return unlink_character_from_series(db, series_id, character_id)
    except AssetLifecycleError as exc:
        raise _lifecycle_http_error(exc)


@router.delete("/{series_id}/scenes/{scene_id}")
def unlink_scene(series_id: str, scene_id: str, db: Session = Depends(get_db),
                 user=Depends(verify_admin_token)):
    try:
        return unlink_scene_from_series(db, series_id, scene_id)
    except AssetLifecycleError as exc:
        raise _lifecycle_http_error(exc)
```

- [ ] **Step 8: Update character and scene delete routes to use lifecycle service**

Modify `server/app/routers/characters.py`:

```python
from fastapi import Query
from app.services.asset_lifecycle_service import AssetLifecycleError, archive_character_or_scene
```

Replace `list_characters` with:

```python
@router.get("")
def list_characters(include_archived: bool = Query(False),
                    db: Session = Depends(get_db),
                    _: str = Depends(verify_admin_token)):
    rows = db.query(Character).all()
    if not include_archived:
        rows = [item for item in rows if not (item.meta_json or {}).get("archived")]
    return {"ok": True, "characters": [_to_dict(c) for c in rows]}
```

Replace `delete_character` body:

```python
@router.delete("/{character_id}")
def delete_character(character_id: str, db: Session = Depends(get_db),
                     user=Depends(verify_admin_token)):
    try:
        return archive_character_or_scene(db, "character", character_id)
    except AssetLifecycleError as exc:
        status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or {},
        })
```

Modify `server/app/routers/scenes.py`:

```python
from fastapi import Query
from app.services.asset_lifecycle_service import AssetLifecycleError, archive_character_or_scene
```

Replace `list_scenes` with:

```python
@router.get("")
def list_scenes(include_archived: bool = Query(False),
                db: Session = Depends(get_db),
                _: str = Depends(verify_admin_token)):
    rows = db.query(Scene).all()
    if not include_archived:
        rows = [item for item in rows if not (item.meta_json or {}).get("archived")]
    return {"ok": True, "scenes": [_to_dict(s) for s in rows]}
```

Replace `delete_scene` body:

```python
@router.delete("/{scene_id}")
def delete_scene(scene_id: str, db: Session = Depends(get_db),
                 user=Depends(verify_admin_token)):
    try:
        return archive_character_or_scene(db, "scene", scene_id)
    except AssetLifecycleError as exc:
        status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or {},
        })
```

- [ ] **Step 9: Run Task 1 backend tests**

Run:

```powershell
pytest server/tests/test_asset_lifecycle_service.py server/tests/test_series_api.py::TestSeriesAPI server/tests/test_asset_archive_api.py -q
```

Expected:

- PASS.

- [ ] **Step 10: Commit Task 1**

Run:

```powershell
git add server/app/services/asset_lifecycle_service.py server/app/routers/series.py server/app/routers/characters.py server/app/routers/scenes.py server/tests/test_asset_lifecycle_service.py server/tests/test_series_api.py server/tests/test_asset_archive_api.py
git commit -m "feat: add safe asset lifecycle management"
```

Expected:

- Commit succeeds with only Task 1 files staged.

---

## Task 2: Backend Reference Image Service

**Provider rule:** Do not ship a provider stub for reference image generation. Move the existing async provider logic from `server/app/routers/series.py::_generate_reference_image` into this service so the new character/scene endpoints use the configured `image_generation` model path, including Pixelle-style providers and Ark/Seedream-style `images/generations` providers. New code must resolve image models through `resolve_image_model_for_capability(db, "image_generation", "text_to_image")`, not through a model-type-only scene lookup.

**Files:**

- Create: `server/app/services/reference_asset_service.py`
- Modify: `server/app/routers/characters.py`
- Modify: `server/app/routers/scenes.py`
- Modify: `server/app/routers/series.py`
- Test: `server/tests/test_reference_asset_service.py`

- [ ] **Step 1: Write failing tests for slot validation and metadata updates**

Create `server/tests/test_reference_asset_service.py`:

```python
import pytest

from app.db_models import Character, Scene
from app.services.reference_asset_service import (
    ReferenceAssetError,
    generate_character_reference_images,
    generate_scene_reference_images,
)


@pytest.mark.asyncio
async def test_invalid_character_slot_raises(db):
    character = Character(name="Lin", role_type="protagonist", gender="female")
    db.add(character)
    db.commit()

    try:
        await generate_character_reference_images(db, character.id, slot="bad_slot")
    except ReferenceAssetError as exc:
        assert exc.code == "REFERENCE_SLOT_INVALID"
    else:
        raise AssertionError("expected ReferenceAssetError")


@pytest.mark.asyncio
async def test_character_reference_generation_updates_single_slot(db, monkeypatch):
    character = Character(
        name="Lin",
        role_type="protagonist",
        gender="female",
        appearance_desc="short black hair",
        outfit_desc="white jacket",
    )
    db.add(character)
    db.commit()

    async def fake_generate(db, prompt, scene_key="image_generation"):
        return "https://cdn.test/lin-front.png"

    monkeypatch.setattr(
        "app.services.reference_asset_service.generate_reference_url",
        fake_generate,
    )

    result = await generate_character_reference_images(db, character.id, slot="avatar_front_url")

    db.refresh(character)
    assert result["ok"] is True
    assert character.avatar_front_url == "https://cdn.test/lin-front.png"
    assert character.meta_json["reference_generation"]["avatar_front_url"]["url"] == "https://cdn.test/lin-front.png"


@pytest.mark.asyncio
async def test_scene_reference_generation_updates_all_slots(db, monkeypatch):
    scene = Scene(
        name="Office",
        scene_type="indoor",
        location_desc="glass office",
        lighting="day",
        mood="tense",
    )
    db.add(scene)
    db.commit()

    async def fake_generate(db, prompt, scene_key="image_generation"):
        if "wide" in prompt.lower():
            return "https://cdn.test/wide.png"
        if "mid" in prompt.lower():
            return "https://cdn.test/mid.png"
        return "https://cdn.test/aerial.png"

    monkeypatch.setattr("app.services.reference_asset_service.generate_reference_url", fake_generate)

    result = await generate_scene_reference_images(db, scene.id, slot="all")

    db.refresh(scene)
    assert result["ok"] is True
    assert scene.reference_wideshot_url == "https://cdn.test/wide.png"
    assert scene.reference_midshot_url == "https://cdn.test/mid.png"
    assert scene.reference_aerial_url == "https://cdn.test/aerial.png"
```

- [ ] **Step 2: Run reference service tests to verify they fail**

Run:

```powershell
pytest server/tests/test_reference_asset_service.py -q
```

Expected:

- FAIL because `reference_asset_service.py` does not exist.

- [ ] **Step 3: Implement reference asset service**

Create `server/app/services/reference_asset_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import Character, Scene
from app.services.pixelle_client import _pixelle_request
from app.services.runtime_model_config import RuntimeModelConfigError, resolve_image_model_for_capability


logger = logging.getLogger(__name__)


CHARACTER_REFERENCE_SLOTS = {
    "avatar_front_url": "front-view character anchor sheet",
    "avatar_side_url": "side-profile character anchor sheet",
    "avatar_threequarter_url": "three-quarter character anchor sheet",
    "avatar_fullbody_url": "full-body costume and proportions anchor sheet",
}

SCENE_REFERENCE_SLOTS = {
    "reference_wideshot_url": "wide establishing scene reference",
    "reference_midshot_url": "mid-shot scene lighting reference",
    "reference_aerial_url": "high-angle environment layout reference",
}


@dataclass
class ReferenceAssetError(ValueError):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def _extract_image_url(payload: dict[str, Any]) -> str | None:
    for key in ("url", "image_url"):
        if payload.get(key):
            return payload[key]
    for key in ("images", "image_urls", "urls"):
        values = payload.get(key)
        if isinstance(values, list) and values:
            first = values[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url") or first.get("image_url")
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0].get("url") or data[0].get("image_url")
    return None


def _record_reference_generation(row: Character | Scene, slot: str, prompt: str, url: str) -> None:
    meta = dict(row.meta_json or {})
    records = dict(meta.get("reference_generation") or {})
    records[slot] = {
        "prompt": prompt,
        "url": url,
        "generated_at": bj_now().isoformat(),
    }
    meta["reference_generation"] = records
    row.meta_json = meta
    row.updated_at = bj_now()


async def generate_reference_url(db: Session, prompt: str, scene_key: str = "image_generation") -> str:
    try:
        model = resolve_image_model_for_capability(db, scene_key, "text_to_image")
    except RuntimeModelConfigError as exc:
        raise ReferenceAssetError(
            "MODEL_SCENE_NOT_CONFIGURED",
            str(exc),
            {"scene_key": scene_key, "capability_key": "text_to_image", "repair_action": "Open AI model config and enable an image-generation model with text_to_image capability."},
        )

    provider = model.get("provider", "")
    model_name = model.get("model_name", "")
    base_url = model.get("base_url", "")
    api_key = model.get("api_key", "")
    cfg = model.get("config_json") or model.get("config") or {}
    if provider in {"comfyui", "pixelle", "runninghub"} or not base_url:
        result = await _pixelle_request("POST", "/api/image/generate", db, json={
            "prompt": prompt,
            "model": model_name or provider,
        })
        url = _extract_image_url(result)
        if url:
            return url
        raise ReferenceAssetError(
            "REFERENCE_PROVIDER_EMPTY_RESULT",
            "Reference image provider returned no usable image URL.",
            {"provider": provider, "model_name": model_name},
        )

    if not api_key:
        raise ReferenceAssetError(
            "MODEL_API_KEY_MISSING",
            "Configured image model is missing API key.",
            {"provider": provider, "model_name": model_name},
        )
    default_size = cfg.get("default_size") or (
        "1440x2560" if provider == "seedance" or "seedream" in model_name.lower() else "1024x1024"
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10), trust_env=False) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model_name or "image",
                "prompt": prompt,
                "n": 1,
                "size": default_size,
                "quality": cfg.get("default_quality", "standard"),
            },
        )
    response.raise_for_status()
    url = _extract_image_url(response.json())
    if not url:
        raise ReferenceAssetError(
            "REFERENCE_PROVIDER_EMPTY_RESULT",
            "Reference image provider returned no usable image URL.",
            {"provider": provider, "model_name": model_name},
        )
    return url


def _slots_to_generate(slot: str, allowed: dict[str, str]) -> list[str]:
    if slot == "all":
        return list(allowed)
    if slot not in allowed:
        raise ReferenceAssetError(
            "REFERENCE_SLOT_INVALID",
            f"Invalid reference image slot: {slot}",
            {"slot": slot, "allowed_slots": list(allowed)},
        )
    return [slot]


def _character_prompt(character: Character, slot: str) -> str:
    label = CHARACTER_REFERENCE_SLOTS[slot]
    return (
        f"{label}, clear face, hairstyle, outfit, stable identity, consistent series style. "
        f"Name: {character.name}. Appearance: {character.appearance_desc or ''}. "
        f"Outfit: {character.outfit_desc or ''}."
    )


def _scene_prompt(scene: Scene, slot: str) -> str:
    label = SCENE_REFERENCE_SLOTS[slot]
    return (
        f"{label}, consistent palette, lighting, environment design, and series style. "
        f"Scene: {scene.name}. Location: {scene.location_desc or ''}. "
        f"Lighting: {scene.lighting or ''}. Mood: {scene.mood or ''}."
    )


async def generate_character_reference_images(db: Session, character_id: str, slot: str = "all") -> dict[str, Any]:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise ReferenceAssetError("ASSET_NOT_FOUND", "Character not found")

    generated: dict[str, str] = {}
    for field in _slots_to_generate(slot, CHARACTER_REFERENCE_SLOTS):
        prompt = _character_prompt(character, field)
        url = await generate_reference_url(db, prompt, scene_key="image_generation")
        setattr(character, field, url)
        _record_reference_generation(character, field, prompt, url)
        generated[field] = url
    db.commit()
    db.refresh(character)
    return {"ok": True, "asset_type": "character", "asset_id": character_id, "generated": generated}


async def generate_scene_reference_images(db: Session, scene_id: str, slot: str = "all") -> dict[str, Any]:
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise ReferenceAssetError("ASSET_NOT_FOUND", "Scene not found")

    generated: dict[str, str] = {}
    for field in _slots_to_generate(slot, SCENE_REFERENCE_SLOTS):
        prompt = _scene_prompt(scene, field)
        url = await generate_reference_url(db, prompt, scene_key="image_generation")
        setattr(scene, field, url)
        _record_reference_generation(scene, field, prompt, url)
        generated[field] = url
    db.commit()
    db.refresh(scene)
    return {"ok": True, "asset_type": "scene", "asset_id": scene_id, "generated": generated}
```

- [ ] **Step 4: Add reference generation route models and endpoints**

Modify `server/app/routers/characters.py`:

```python
from app.services.reference_asset_service import (
    ReferenceAssetError,
    generate_character_reference_images,
)


class ReferenceGenerateInput(BaseModel):
    slot: str = "all"
```

Add endpoint:

```python
@router.post("/{character_id}/reference-images/generate")
async def generate_character_references(character_id: str, body: ReferenceGenerateInput,
                                        db: Session = Depends(get_db),
                                        user=Depends(verify_admin_token)):
    try:
        return await generate_character_reference_images(db, character_id, slot=body.slot)
    except ReferenceAssetError as exc:
        status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or {},
        })
```

Modify `server/app/routers/scenes.py`:

```python
from app.services.reference_asset_service import (
    ReferenceAssetError,
    generate_scene_reference_images,
)


class ReferenceGenerateInput(BaseModel):
    slot: str = "all"
```

Add endpoint:

```python
@router.post("/{scene_id}/reference-images/generate")
async def generate_scene_references(scene_id: str, body: ReferenceGenerateInput,
                                    db: Session = Depends(get_db),
                                    user=Depends(verify_admin_token)):
    try:
        return await generate_scene_reference_images(db, scene_id, slot=body.slot)
    except ReferenceAssetError as exc:
        status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or {},
        })
```

- [ ] **Step 5: Run reference service tests**

Run:

```powershell
pytest server/tests/test_reference_asset_service.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add server/app/services/reference_asset_service.py server/app/routers/characters.py server/app/routers/scenes.py server/tests/test_reference_asset_service.py
git commit -m "feat: add reference image generation service"
```

Expected:

- Commit succeeds with only Task 2 files staged.

---

## Task 3: Backend AI Rewrite Candidates

**Files:**

- Create: `server/app/services/asset_ai_rewrite_service.py`
- Modify: `server/app/routers/characters.py`
- Modify: `server/app/routers/scenes.py`
- Test: `server/tests/test_asset_ai_rewrite_service.py`

- [ ] **Step 1: Write failing AI rewrite tests**

Create `server/tests/test_asset_ai_rewrite_service.py`:

```python
import pytest

from app.db_models import Character, Scene
from app.services.asset_ai_rewrite_service import rewrite_character_candidate, rewrite_scene_candidate


@pytest.mark.asyncio
async def test_rewrite_character_returns_candidate_without_saving(db, monkeypatch):
    character = Character(
        name="Lin",
        role_type="protagonist",
        gender="female",
        personality="quiet",
        appearance_desc="short hair",
        outfit_desc="white jacket",
    )
    db.add(character)
    db.commit()

    async def fake_generate_custom(db, system, prompt, max_tokens=4096, temperature=0.5):
        return '{"name":"Lin","role_type":"protagonist","gender":"female","personality":"brave","appearance_desc":"short black hair, sharp eyes","outfit_desc":"white jacket with blue trim","default_voice_id":"voice-1"}'

    monkeypatch.setattr("app.services.asset_ai_rewrite_service.ai_generator.generate_custom", fake_generate_custom)

    result = await rewrite_character_candidate(db, character.id, instruction="make her stronger")

    db.refresh(character)
    assert result["ok"] is True
    assert result["candidate"]["personality"] == "brave"
    assert character.personality == "quiet"


@pytest.mark.asyncio
async def test_rewrite_scene_returns_candidate_without_saving(db, monkeypatch):
    scene = Scene(name="Office", scene_type="indoor", location_desc="plain office", lighting="day", mood="tense")
    db.add(scene)
    db.commit()

    async def fake_generate_custom(db, system, prompt, max_tokens=4096, temperature=0.5):
        return '{"name":"Office","scene_type":"indoor","location_desc":"glass office with city skyline","lighting":"day","mood":"tense"}'

    monkeypatch.setattr("app.services.asset_ai_rewrite_service.ai_generator.generate_custom", fake_generate_custom)

    result = await rewrite_scene_candidate(db, scene.id, instruction="make it cinematic")

    db.refresh(scene)
    assert result["ok"] is True
    assert result["candidate"]["location_desc"] == "glass office with city skyline"
    assert scene.location_desc == "plain office"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest server/tests/test_asset_ai_rewrite_service.py -q
```

Expected:

- FAIL because `asset_ai_rewrite_service.py` does not exist.

- [ ] **Step 3: Implement AI rewrite service**

Create `server/app/services/asset_ai_rewrite_service.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import Character, Scene
from app.services.ai_generator import ai_generator


@dataclass
class AssetRewriteError(ValueError):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise AssetRewriteError("AI_REWRITE_PARSE_FAILED", "AI rewrite result is not valid JSON")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise AssetRewriteError("AI_REWRITE_PARSE_FAILED", "AI rewrite result must be a JSON object")
    return parsed


def _pick_fields(source: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: source[key] for key in allowed if key in source}


async def rewrite_character_candidate(db: Session, character_id: str, instruction: str = "") -> dict[str, Any]:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise AssetRewriteError("ASSET_NOT_FOUND", "Character not found")

    system = "你是短剧角色资产设计师。只返回 JSON 对象，不要 Markdown。"
    prompt = f"""
基于当前角色档案生成一个可编辑候选，不要删除角色身份。
当前档案：
name={character.name}
role_type={character.role_type}
gender={character.gender}
age_range={character.age_range or ""}
personality={character.personality or ""}
appearance_desc={character.appearance_desc or ""}
outfit_desc={character.outfit_desc or ""}
default_voice_id={character.default_voice_id or ""}
修改要求：{instruction or "优化为更适合 AI 视频生成的一致性角色档案"}

返回字段：name, role_type, gender, age_range, personality, appearance_desc, outfit_desc, default_voice_id。
"""
    raw = await ai_generator.generate_custom(db, system, prompt, max_tokens=4096, temperature=0.5)
    candidate = _pick_fields(_parse_json_object(raw), {
        "name", "role_type", "gender", "age_range", "personality",
        "appearance_desc", "outfit_desc", "default_voice_id",
    })
    return {"ok": True, "asset_type": "character", "asset_id": character_id, "candidate": candidate}


async def rewrite_scene_candidate(db: Session, scene_id: str, instruction: str = "") -> dict[str, Any]:
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise AssetRewriteError("ASSET_NOT_FOUND", "Scene not found")

    system = "你是短剧场景资产设计师。只返回 JSON 对象，不要 Markdown。"
    prompt = f"""
基于当前场景档案生成一个可编辑候选，保持场景用途稳定。
当前档案：
name={scene.name}
scene_type={scene.scene_type}
location_desc={scene.location_desc or ""}
lighting={scene.lighting or ""}
mood={scene.mood or ""}
修改要求：{instruction or "优化为更适合 AI 视频生成的一致性场景档案"}

返回字段：name, scene_type, location_desc, lighting, mood。
"""
    raw = await ai_generator.generate_custom(db, system, prompt, max_tokens=4096, temperature=0.5)
    candidate = _pick_fields(_parse_json_object(raw), {
        "name", "scene_type", "location_desc", "lighting", "mood",
    })
    return {"ok": True, "asset_type": "scene", "asset_id": scene_id, "candidate": candidate}
```

- [ ] **Step 4: Add AI rewrite route models and endpoints**

Modify `server/app/routers/characters.py`:

```python
from app.services.asset_ai_rewrite_service import (
    AssetRewriteError,
    rewrite_character_candidate,
)


class AiRewriteInput(BaseModel):
    instruction: str = ""
```

Add endpoint:

```python
@router.post("/{character_id}/ai-rewrite")
async def ai_rewrite_character(character_id: str, body: AiRewriteInput,
                               db: Session = Depends(get_db),
                               user=Depends(verify_admin_token)):
    try:
        return await rewrite_character_candidate(db, character_id, instruction=body.instruction)
    except AssetRewriteError as exc:
        status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or {},
        })
```

Modify `server/app/routers/scenes.py`:

```python
from app.services.asset_ai_rewrite_service import (
    AssetRewriteError,
    rewrite_scene_candidate,
)


class AiRewriteInput(BaseModel):
    instruction: str = ""
```

Add endpoint:

```python
@router.post("/{scene_id}/ai-rewrite")
async def ai_rewrite_scene(scene_id: str, body: AiRewriteInput,
                           db: Session = Depends(get_db),
                           user=Depends(verify_admin_token)):
    try:
        return await rewrite_scene_candidate(db, scene_id, instruction=body.instruction)
    except AssetRewriteError as exc:
        status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details or {},
        })
```

- [ ] **Step 5: Run AI rewrite tests**

Run:

```powershell
pytest server/tests/test_asset_ai_rewrite_service.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add server/app/services/asset_ai_rewrite_service.py server/app/routers/characters.py server/app/routers/scenes.py server/tests/test_asset_ai_rewrite_service.py
git commit -m "feat: add AI rewrite candidates for assets"
```

Expected:

- Commit succeeds with only Task 3 files staged.

---

## Task 4: Backend Review Asset Void And Image Edit

**Provider rule:** The image edit endpoint must call the configured `image_editing` capability through the existing image creation/provider path. The test seam may monkeypatch `_generate_edited_image`, but the production implementation must execute valid configured providers instead of ending at a dead-end error. Image edit is an async provider lifecycle: do not assume the edited image is available in the same request when the image task is queued or still running.

**Files:**

- Create: `server/app/services/review_asset_edit_service.py`
- Modify: `server/app/routers/video_production.py`
- Test: `server/tests/test_review_asset_edit_service.py`
- Modify: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Write failing service tests for void and image edit versioning**

Create `server/tests/test_review_asset_edit_service.py`:

```python
import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.review_asset_edit_service import ReviewAssetEditError, edit_image_asset, void_asset_version


def create_run_with_image_asset(db):
    series = Series(title="Series", logline="Story", genre="drama", total_episodes=1, target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "old prompt"}]},
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image",
        url="https://cdn.test/old.png",
        version=1,
        status="review_pending",
        is_latest=True,
        copy_status="persisted",
        checksum="abc",
        storage_path="assets/old.png",
        metadata_json={"storyboard_frame": {"frame_id": "frame-001", "image_prompt": "old prompt"}},
    )
    db.add(asset)
    db.commit()
    return run, asset


def test_void_asset_version_marks_asset_voided_and_records_review(db):
    _, asset = create_run_with_image_asset(db)

    result = void_asset_version(db, asset.id, reviewer_user_id="user-1", comment="bad face")

    db.refresh(asset)
    review = db.query(VideoReviewRecord).filter(VideoReviewRecord.asset_id == asset.id).one()
    assert result["ok"] is True
    assert asset.status == "voided"
    assert review.action == "void"
    assert review.comment == "bad face"


@pytest.mark.asyncio
async def test_edit_image_asset_creates_new_version(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)

    async def fake_generate(db, asset, instruction):
        return {
            "url": "https://cdn.test/new.png",
            "source_url": asset.url,
            "metadata": {"edit_instruction": instruction},
        }

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    result = await edit_image_asset(db, asset.id, instruction="make hair consistent")

    db.refresh(asset)
    new_asset = result["asset"]
    assert asset.is_latest is False
    assert new_asset.version == 2
    assert new_asset.status == "review_pending"
    assert new_asset.run_id == asset.run_id
    assert new_asset.episode_id == asset.episode_id
    assert new_asset.frame_id == asset.frame_id
    assert new_asset.metadata_json["source_asset_id"] == asset.id


@pytest.mark.asyncio
async def test_edit_image_asset_surfaces_queued_task(db, monkeypatch):
    _, asset = create_run_with_image_asset(db)

    async def fake_generate(db, asset, instruction):
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_QUEUED",
            "Image edit task is queued.",
            {"image_task_id": "task-1", "status": "queued"},
        )

    monkeypatch.setattr("app.services.review_asset_edit_service._generate_edited_image", fake_generate)

    with pytest.raises(ReviewAssetEditError) as exc:
        await edit_image_asset(db, asset.id, instruction="make hair consistent")

    assert exc.value.code == "IMAGE_EDIT_TASK_QUEUED"
    db.refresh(asset)
    assert asset.is_latest is True
    assert db.query(VideoProductionAsset).count() == 1


def test_void_stale_asset_version_raises(db):
    _, asset = create_run_with_image_asset(db)
    asset.is_latest = False
    db.commit()

    with pytest.raises(ReviewAssetEditError) as exc:
        void_asset_version(db, asset.id, reviewer_user_id="user-1", comment="old")

    assert exc.value.code == "STALE_ASSET_VERSION"


@pytest.mark.asyncio
async def test_edit_stale_asset_version_raises(db):
    _, asset = create_run_with_image_asset(db)
    asset.is_latest = False
    db.commit()

    with pytest.raises(ReviewAssetEditError) as exc:
        await edit_image_asset(db, asset.id, instruction="make hair consistent")

    assert exc.value.code == "STALE_ASSET_VERSION"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest server/tests/test_review_asset_edit_service.py -q
```

Expected:

- FAIL because `review_asset_edit_service.py` does not exist.

- [ ] **Step 3: Implement review asset edit service**

Create `server/app/services/review_asset_edit_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import VideoProductionAsset, VideoProductionRun, VideoReviewRecord


@dataclass
class ReviewAssetEditError(ValueError):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def _asset_snapshot(asset: VideoProductionAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "frame_id": asset.frame_id,
        "asset_type": asset.asset_type,
        "stage": asset.stage,
        "url": asset.url,
        "version": asset.version,
        "status": asset.status,
        "is_latest": asset.is_latest,
    }


def _load_asset(db: Session, asset_id: str) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise ReviewAssetEditError("ASSET_NOT_FOUND", "Asset not found")
    return asset


def void_asset_version(
    db: Session,
    asset_id: str,
    reviewer_user_id: str | None = None,
    comment: str = "",
    expected_version: int | None = None,
) -> dict[str, Any]:
    asset = _load_asset(db, asset_id)
    if expected_version is not None and asset.version != expected_version:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "The submitted asset version is no longer current")
    if not asset.is_latest:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "Only the latest asset version can be voided")
    if asset.status not in {"review_pending", "rejected", "failed", "regenerating"}:
        raise ReviewAssetEditError("ASSET_STATUS_NOT_VOIDABLE", f"Asset status is not voidable: {asset.status}")

    asset.status = "voided"
    asset.updated_at = bj_now()
    review = VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="voided",
        reviewer_user_id=reviewer_user_id,
        action="void",
        comment=comment,
        asset_snapshot_json=_asset_snapshot(asset),
        asset_version=asset.version,
        is_latest_asset_review=True,
        target_type=asset.target_type,
        target_id=asset.target_id,
        production_segment_id=asset.production_segment_id,
    )
    db.add(review)
    db.commit()
    db.refresh(asset)
    return {"ok": True, "asset": asset, "review_id": review.id}


async def _generate_edited_image(db: Session, asset: VideoProductionAsset, instruction: str) -> dict[str, Any]:
    from app.db_models import ImageCreationAsset
    from app.services.image_creation_service import create_image_task, sync_image_task

    task = await create_image_task(db, {
        "mode": "image_to_image",
        "prompt": instruction,
        "source": {"type": "url", "url": asset.url},
        "source_url": asset.url,
        "count": 1,
        "destination_role": "video_production_review_edit",
        "destination_context": {
            "video_asset_id": asset.id,
            "run_id": asset.run_id,
            "frame_id": asset.frame_id,
        },
        "idempotency_key": f"video-review-edit:{asset.id}:{asset.version}:{instruction}",
        "cost_confirmation": True,
    })
    if task.status == "queued" and not task.pixelle_task_id:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_QUEUED",
            "Image edit task is queued and has not been submitted to the provider yet.",
            {"image_task_id": task.id, "status": task.status},
        )
    if task.pixelle_task_id:
        task = await sync_image_task(db, task.id)
    asset_row = (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == task.id)
        .filter(ImageCreationAsset.status.in_(["review_pending", "approved", "generated"]))
        .order_by(ImageCreationAsset.created_at.desc())
        .first()
    )
    if not asset_row or not asset_row.url:
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_PENDING",
            "Image edit task has not produced a usable image URL yet.",
            {"image_task_id": task.id, "status": task.status},
        )
    return {
        "url": asset_row.url,
        "source_url": asset.url,
        "metadata": {
            "image_creation_task_id": task.id,
            "image_creation_asset_id": asset_row.id,
            "edit_instruction": instruction,
        },
        "storage_path": asset_row.storage_path,
        "checksum": asset_row.checksum,
        "size_bytes": asset_row.size_bytes,
        "copy_status": asset_row.storage_status or "registered",
    }


async def edit_image_asset(
    db: Session,
    asset_id: str,
    instruction: str,
    expected_version: int | None = None,
) -> dict[str, Any]:
    asset = _load_asset(db, asset_id)
    if asset.asset_type != "image":
        raise ReviewAssetEditError("IMAGE_EDIT_UNSUPPORTED", "Only image assets can be edited")
    if expected_version is not None and asset.version != expected_version:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "The submitted asset version is no longer current")
    if not asset.is_latest:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "Only the latest asset version can be edited")

    generated = await _generate_edited_image(db, asset, instruction)
    current_latest = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == asset.run_id,
        VideoProductionAsset.frame_id == asset.frame_id,
        VideoProductionAsset.asset_type == asset.asset_type,
        VideoProductionAsset.is_latest.is_(True),
    ).with_for_update().first()
    if not current_latest or current_latest.id != asset.id:
        raise ReviewAssetEditError("STALE_ASSET_VERSION", "A newer asset version already exists")

    latest_version = db.query(func.max(VideoProductionAsset.version)).filter(
        VideoProductionAsset.run_id == asset.run_id,
        VideoProductionAsset.frame_id == asset.frame_id,
        VideoProductionAsset.asset_type == asset.asset_type,
    ).scalar() or asset.version

    metadata = dict(asset.metadata_json or {})
    new_metadata = dict(generated.get("metadata") or {})
    new_metadata.update({
        "source_asset_id": asset.id,
        "source_version": asset.version,
        "edit_instruction": instruction,
        "storyboard_frame": metadata.get("storyboard_frame"),
    })
    new_asset = VideoProductionAsset(
        run_id=asset.run_id,
        episode_id=asset.episode_id,
        frame_id=asset.frame_id,
        asset_type=asset.asset_type,
        stage=asset.stage,
        url=generated.get("url"),
        source_url=generated.get("source_url") or asset.url,
        version=int(latest_version) + 1,
        source_version=asset.version,
        metadata_json=new_metadata,
        status="review_pending",
        is_latest=True,
        target_type=asset.target_type,
        target_id=asset.target_id,
        production_segment_id=asset.production_segment_id,
        production_shot_id=asset.production_shot_id,
        copy_status=generated.get("copy_status", "registered"),
        checksum=generated.get("checksum"),
        storage_path=generated.get("storage_path"),
        size_bytes=generated.get("size_bytes"),
    )
    db.add(new_asset)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ReviewAssetEditError(
            "STALE_ASSET_VERSION",
            "Another edit created a newer asset version first.",
            {"run_id": asset.run_id, "frame_id": asset.frame_id, "asset_type": asset.asset_type},
        ) from exc
    asset.is_latest = False
    asset.updated_at = bj_now()
    db.commit()
    db.refresh(new_asset)
    db.refresh(asset)
    return {"ok": True, "asset": new_asset}
```

- [ ] **Step 4: Add video production route models and endpoints**

Modify `server/app/routers/video_production.py`.

Add imports:

```python
from fastapi.responses import JSONResponse
from app.services.review_asset_edit_service import (
    ReviewAssetEditError,
    edit_image_asset,
    void_asset_version,
)
```

Add request models:

```python
class VoidAssetRequest(BaseModel):
    comment: str = ""
    expected_version: int | None = None


class ImageEditRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)
    expected_version: int | None = None
```

Add helper:

```python
def _review_edit_pending_response(exc: ReviewAssetEditError) -> JSONResponse:
    details = exc.details or {}
    return JSONResponse(status_code=202, content={
        "ok": False,
        "status": "pending",
        "code": exc.code,
        "message": "改图任务已提交，等待生成结果同步。",
        "image_creation_task_id": details.get("image_task_id"),
        "warnings": [{"code": exc.code, "message": exc.message, "details": details}],
        "missing_requirements": [],
    })


def _review_edit_http_error(exc: ReviewAssetEditError) -> HTTPException:
    status = 404 if exc.code == "ASSET_NOT_FOUND" else 409
    return HTTPException(status_code=status, detail={
        "code": exc.code,
        "message": exc.message,
        "details": exc.details or {},
    })
```

Add endpoints near human review actions:

```python
@router.post("/assets/{asset_id}/void")
def void_asset(asset_id: str, body: VoidAssetRequest,
               db: Session = Depends(get_db),
               user=Depends(verify_admin_token)):
    reviewer_id = user[0] if isinstance(user, tuple) else None
    try:
        result = void_asset_version(
            db,
            asset_id,
            reviewer_user_id=reviewer_id,
            comment=body.comment,
            expected_version=body.expected_version,
        )
    except ReviewAssetEditError as exc:
        raise _review_edit_http_error(exc)
    return {"ok": True, "asset": _asset_payload(result["asset"]), "warnings": [], "missing_requirements": []}


@router.post("/assets/{asset_id}/image-edit")
async def image_edit_asset(asset_id: str, body: ImageEditRequest,
                           db: Session = Depends(get_db),
                           user=Depends(verify_admin_token)):
    try:
        result = await edit_image_asset(
            db,
            asset_id,
            instruction=body.instruction,
            expected_version=body.expected_version,
        )
    except ReviewAssetEditError as exc:
        if exc.code in {"IMAGE_EDIT_TASK_QUEUED", "IMAGE_EDIT_TASK_PENDING"}:
            return _review_edit_pending_response(exc)
        raise _review_edit_http_error(exc)
    return {"ok": True, "asset": _asset_payload(result["asset"]), "warnings": [], "missing_requirements": []}
```

- [ ] **Step 5: Include reference evidence in review item payloads**

Modify `_asset_payload` in `server/app/routers/video_production.py` to add:

```python
"reference_evidence": _reference_evidence_from_storyboard(storyboard_frame),
```

Add helper near `_storyboard_frame`:

```python
def _reference_evidence_from_storyboard(frame: dict) -> dict:
    return {
        "reference_urls": frame.get("reference_urls") or [],
        "character_reference_urls": frame.get("character_reference_urls") or [],
        "style_reference_urls": frame.get("style_reference_urls") or [],
        "scene_id": frame.get("scene_id"),
        "character_ids": frame.get("character_ids") or [],
    }
```

Append API-level tests to `server/tests/test_video_production_api.py`:

```python
from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun
from app.services.review_asset_edit_service import ReviewAssetEditError


def create_run_with_image_asset(db):
    series = Series(title="Series", logline="Story", genre="drama", total_episodes=1, target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(series_id=series.id, episode_number=1, status="pending")
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_review_pending",
        current_stage="image_review",
        storyboard_json={"frames": [{"frame_id": "frame-001", "reference_urls": ["https://cdn.test/ref.png"]}]},
    )
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image",
        url="https://cdn.test/old.png",
        version=1,
        status="review_pending",
        is_latest=True,
        copy_status="persisted",
        checksum="abc",
        storage_path="assets/old.png",
    )
    db.add(asset)
    db.commit()
    return run, asset


def test_image_edit_pending_response_has_sync_payload(client, monkeypatch, db):
    _, asset = create_run_with_image_asset(db)

    async def fake_edit(db, asset_id, instruction, expected_version=None):
        raise ReviewAssetEditError(
            "IMAGE_EDIT_TASK_QUEUED",
            "Image edit task is queued.",
            {"image_task_id": "task-1", "status": "queued"},
        )

    monkeypatch.setattr("app.routers.video_production.edit_image_asset", fake_edit)

    resp = client.post(f"/api/video-production/assets/{asset.id}/image-edit", json={
        "instruction": "保持角色脸型一致",
        "expected_version": asset.version,
    })

    assert resp.status_code == 202
    data = resp.json()
    assert data["ok"] is False
    assert data["status"] == "pending"
    assert data["image_creation_task_id"] == "task-1"
    assert data["warnings"][0]["code"] == "IMAGE_EDIT_TASK_QUEUED"
    assert data["missing_requirements"] == []


def test_void_asset_rejects_stale_expected_version(client, db):
    _, asset = create_run_with_image_asset(db)

    resp = client.post(f"/api/video-production/assets/{asset.id}/void", json={
        "comment": "old version",
        "expected_version": asset.version - 1,
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "STALE_ASSET_VERSION"
```

- [ ] **Step 6: Run review edit tests**

Run:

```powershell
pytest server/tests/test_review_asset_edit_service.py server/tests/test_video_production_api.py -q
```

Expected:

- PASS for new service tests and existing video production API tests.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add server/app/services/review_asset_edit_service.py server/app/routers/video_production.py server/tests/test_review_asset_edit_service.py server/tests/test_video_production_api.py
git commit -m "feat: add review asset edit and void actions"
```

Expected:

- Commit succeeds with only Task 4 files staged.

---

## Task 5: Frontend API Clients And Shared Components

**Design review correction:** Build these components as product-workbench UI, not as a new decorative card set. Use the existing slate dark surfaces, compact typography, and existing primitives where they fit: `AppDialog.vue` for modal semantics, `AppButton.vue` for action styling, `EmptyState.vue` for empty surfaces, and `StatusBadge.vue` for status labels. New components may add layout behavior, but they must not introduce a second button system, hover-only discovery, or placeholder-only form labels.

**Files:**

- Modify: `web/src/api/series.js`
- Modify: `web/src/api/characters.js`
- Modify: `web/src/api/scenes.js`
- Modify: `web/src/api/videoProduction.js`
- Create: `web/src/components/assets/DangerConfirmDialog.vue`
- Create: `web/src/components/assets/AssetDetailDrawer.vue`
- Create: `web/src/components/assets/ReferenceImageGallery.vue`
- Create: `web/src/components/assets/AiRewriteConfirmDialog.vue`
- Test: `web/src/__tests__/asset-detail-drawer.test.js`
- Test: `web/src/__tests__/reference-image-gallery.test.js`

- [ ] **Step 1: Write failing component tests**

Create `web/src/__tests__/reference-image-gallery.test.js`:

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import ReferenceImageGallery from '../components/assets/ReferenceImageGallery.vue'

describe('ReferenceImageGallery', () => {
  it('shows Chinese empty state and emits regenerate for one slot', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          { key: 'avatar_front_url', label: '正面', url: '' },
        ],
        loadingSlot: '',
      },
    })

    expect(wrapper.text()).toContain('待生成')
    await wrapper.find('[data-test="regenerate-avatar_front_url"]').trigger('click')
    expect(wrapper.emitted('regenerate')[0]).toEqual(['avatar_front_url'])
  })

  it('emits replace-url with typed URL', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '场景参考图',
        slots: [
          { key: 'reference_wideshot_url', label: '广角', url: 'https://old.test/a.png' },
        ],
        loadingSlot: '',
      },
    })

    await wrapper.find('[data-test="edit-reference_wideshot_url"]').trigger('click')
    await wrapper.find('[data-test="url-input-reference_wideshot_url"]').setValue('https://new.test/a.png')
    await wrapper.find('[data-test="save-url-reference_wideshot_url"]').trigger('click')

    expect(wrapper.emitted('replace-url')[0]).toEqual(['reference_wideshot_url', 'https://new.test/a.png'])
  })
})
```

Create `web/src/__tests__/asset-detail-drawer.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import AssetDetailDrawer from '../components/assets/AssetDetailDrawer.vue'

describe('AssetDetailDrawer', () => {
  it('renders Chinese title and emits close', async () => {
    const wrapper = mount(AssetDetailDrawer, {
      props: {
        open: true,
        title: '角色详情',
        subtitle: '林岚',
      },
      slots: {
        default: '<div data-test="drawer-body">内容</div>',
      },
    })

    expect(wrapper.text()).toContain('角色详情')
    expect(wrapper.text()).toContain('林岚')
    await wrapper.find('[data-test="close-drawer"]').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run component tests to verify they fail**

Run:

```powershell
cd web
npx vitest run src/__tests__/reference-image-gallery.test.js src/__tests__/asset-detail-drawer.test.js
```

Expected:

- FAIL because the components do not exist.

- [ ] **Step 3: Add API client functions**

Modify `web/src/api/series.js`:

```javascript
export function updateSeries(id, data) { return client.put(`/series/${id}`, data) }
export function unlinkCharacter(seriesId, characterId) { return client.delete(`/series/${seriesId}/characters/${characterId}`) }
export function unlinkScene(seriesId, sceneId) { return client.delete(`/series/${seriesId}/scenes/${sceneId}`) }
```

Modify `web/src/api/characters.js`:

```javascript
export function aiRewriteCharacter(id, data) { return client.post(`/characters/${id}/ai-rewrite`, data) }
export function generateCharacterReferences(id, data) { return client.post(`/characters/${id}/reference-images/generate`, data) }
```

Modify `web/src/api/scenes.js`:

```javascript
export function aiRewriteScene(id, data) { return client.post(`/scenes/${id}/ai-rewrite`, data) }
export function generateSceneReferences(id, data) { return client.post(`/scenes/${id}/reference-images/generate`, data) }
```

Modify `web/src/api/videoProduction.js`:

```javascript
export function voidProductionAsset(assetId, payload = {}) {
  return client.post(`/video-production/assets/${assetId}/void`, payload)
}

export function imageEditProductionAsset(assetId, payload) {
  return client.post(`/video-production/assets/${assetId}/image-edit`, payload)
}
```

- [ ] **Step 4: Create shared drawer component**

Create `web/src/components/assets/AssetDetailDrawer.vue`:

```vue
<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex justify-end bg-black/60" @click.self="$emit('close')">
      <aside class="flex h-full w-full max-w-2xl flex-col border-l border-slate-700 bg-slate-950 shadow-2xl">
        <header class="flex items-start justify-between border-b border-slate-800 px-5 py-4">
          <div class="min-w-0">
            <h2 class="text-lg font-semibold text-slate-100">{{ title }}</h2>
            <p v-if="subtitle" class="mt-1 truncate text-sm text-slate-400">{{ subtitle }}</p>
          </div>
          <button
            data-test="close-drawer"
            type="button"
            class="rounded border border-slate-700 px-3 py-1 text-sm text-slate-300 hover:bg-slate-800"
            @click="$emit('close')"
          >
            关闭
          </button>
        </header>
        <main class="min-h-0 flex-1 overflow-y-auto p-5">
          <slot />
        </main>
        <footer v-if="$slots.footer" class="border-t border-slate-800 p-4">
          <slot name="footer" />
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})

defineEmits(['close'])
</script>
```

- [ ] **Step 5: Create reference image gallery component**

Create `web/src/components/assets/ReferenceImageGallery.vue`:

```vue
<template>
  <section class="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
    <div class="mb-3 flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-slate-100">{{ title }}</h3>
      <button
        type="button"
        class="rounded bg-sky-600 px-3 py-1.5 text-xs text-white hover:bg-sky-500 disabled:opacity-50"
        :disabled="Boolean(loadingSlot)"
        @click="$emit('regenerate', 'all')"
      >
        全部重生成
      </button>
    </div>

    <div class="grid gap-3 sm:grid-cols-2">
      <article v-for="slot in slots" :key="slot.key" class="rounded border border-slate-800 bg-slate-900/60 p-3">
        <div class="mb-2 flex items-center justify-between gap-2">
          <span class="text-sm text-slate-200">{{ slot.label }}</span>
          <span class="text-xs" :class="slot.url ? 'text-emerald-300' : 'text-amber-300'">
            {{ slot.url ? '已生成' : '待生成' }}
          </span>
        </div>

        <button
          v-if="slot.url"
          type="button"
          class="mb-3 flex aspect-[9/12] w-full items-center justify-center overflow-hidden rounded bg-slate-950"
          @click="previewUrl = slot.url"
        >
          <img :src="slot.url" :alt="slot.label" class="h-full w-full object-contain" />
        </button>
        <div v-else class="mb-3 flex aspect-[9/12] items-center justify-center rounded bg-slate-950 text-xs text-slate-500">
          暂无参考图
        </div>

        <div class="flex flex-wrap gap-2">
          <button
            :data-test="`regenerate-${slot.key}`"
            type="button"
            class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            :disabled="loadingSlot === slot.key || loadingSlot === 'all'"
            @click="$emit('regenerate', slot.key)"
          >
            {{ loadingSlot === slot.key ? '生成中' : '重生成' }}
          </button>
          <button
            v-if="slot.url"
            type="button"
            class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
            @click="copy(slot.url)"
          >
            复制 URL
          </button>
          <button
            :data-test="`edit-${slot.key}`"
            type="button"
            class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:bg-slate-800"
            @click="editingKey = slot.key; editingUrl = slot.url || ''"
          >
            替换 URL
          </button>
        </div>

        <div v-if="editingKey === slot.key" class="mt-3 space-y-2">
          <input
            :data-test="`url-input-${slot.key}`"
            v-model="editingUrl"
            class="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            placeholder="https://..."
          />
          <div class="flex gap-2">
            <button
              :data-test="`save-url-${slot.key}`"
              type="button"
              class="rounded bg-emerald-600 px-3 py-1.5 text-xs text-white"
              @click="saveUrl(slot.key)"
            >
              保存
            </button>
            <button type="button" class="rounded border border-slate-700 px-3 py-1.5 text-xs text-slate-300" @click="editingKey = ''">
              取消
            </button>
          </div>
        </div>
      </article>
    </div>

    <div v-if="previewUrl" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-6" @click.self="previewUrl = ''">
      <img :src="previewUrl" alt="参考图预览" class="max-h-full max-w-full object-contain" />
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  title: { type: String, required: true },
  slots: { type: Array, required: true },
  loadingSlot: { type: String, default: '' },
})

const emit = defineEmits(['regenerate', 'replace-url'])
const previewUrl = ref('')
const editingKey = ref('')
const editingUrl = ref('')

function copy(url) {
  navigator.clipboard?.writeText(url)
}

function saveUrl(key) {
  emit('replace-url', key, editingUrl.value)
  editingKey.value = ''
}
</script>
```

- [ ] **Step 6: Create confirmation dialog components**

Create `web/src/components/assets/DangerConfirmDialog.vue`:

```vue
<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="$emit('cancel')">
    <section class="w-full max-w-md rounded-lg border border-rose-900/60 bg-slate-950 p-5 shadow-2xl">
      <h2 class="text-lg font-semibold text-slate-100">{{ title }}</h2>
      <p class="mt-2 whitespace-pre-wrap text-sm text-slate-300">{{ message }}</p>
      <div class="mt-5 flex justify-end gap-2">
        <button type="button" class="rounded border border-slate-700 px-4 py-2 text-sm text-slate-300" @click="$emit('cancel')">
          取消
        </button>
        <button type="button" class="rounded bg-rose-600 px-4 py-2 text-sm text-white hover:bg-rose-500" @click="$emit('confirm')">
          {{ confirmText }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '确认操作' },
  message: { type: String, required: true },
  confirmText: { type: String, default: '确认' },
})

defineEmits(['confirm', 'cancel'])
</script>
```

Create `web/src/components/assets/AiRewriteConfirmDialog.vue`:

```vue
<template>
  <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="$emit('cancel')">
    <section class="w-full max-w-2xl rounded-lg border border-slate-800 bg-slate-950 p-5 shadow-2xl">
      <h2 class="text-lg font-semibold text-slate-100">{{ title }}</h2>
      <div class="mt-4 grid gap-3">
        <label v-for="field in fields" :key="field.key" class="grid gap-1">
          <span class="text-xs text-slate-400">{{ field.label }}</span>
          <textarea
            v-if="field.multiline"
            v-model="draft[field.key]"
            rows="3"
            class="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
          />
          <input
            v-else
            v-model="draft[field.key]"
            class="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
          />
        </label>
      </div>
      <div class="mt-5 flex justify-end gap-2">
        <button type="button" class="rounded border border-slate-700 px-4 py-2 text-sm text-slate-300" @click="$emit('cancel')">
          取消
        </button>
        <button type="button" class="rounded bg-emerald-600 px-4 py-2 text-sm text-white" @click="$emit('confirm', { ...draft })">
          应用候选
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: 'AI 重写候选' },
  candidate: { type: Object, default: () => ({}) },
  fields: { type: Array, required: true },
})

defineEmits(['confirm', 'cancel'])

const draft = reactive({})

watch(
  () => props.candidate,
  value => {
    for (const key of Object.keys(draft)) delete draft[key]
    Object.assign(draft, value || {})
  },
  { immediate: true },
)
</script>
```

- [ ] **Step 7: Run component tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/reference-image-gallery.test.js src/__tests__/asset-detail-drawer.test.js
```

Expected:

- PASS.

- [ ] **Step 8: Commit Task 5**

Run:

```powershell
git add web/src/api/series.js web/src/api/characters.js web/src/api/scenes.js web/src/api/videoProduction.js web/src/components/assets web/src/__tests__/reference-image-gallery.test.js web/src/__tests__/asset-detail-drawer.test.js
git commit -m "feat: add asset management frontend primitives"
```

Expected:

- Commit succeeds with only Task 5 files staged.

---

## Task 6: Character And Scene Management Pages

**Files:**

- Modify: `web/src/views/CharactersPage.vue`
- Modify: `web/src/views/ScenesPage.vue`
- Test: `web/src/__tests__/characters-management-page.test.js`
- Test: `web/src/__tests__/scenes-management-page.test.js`

- [ ] **Step 1: Write failing character page test**

Create `web/src/__tests__/characters-management-page.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  updateCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  deleteCharacter: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
  generateCharacterReferences: vi.fn(() => Promise.resolve({ data: { ok: true, generated: { avatar_front_url: 'https://cdn.test/front.png' } } })),
}))

vi.mock('../api/characters.js', () => ({
  listCharacters: vi.fn(() => Promise.resolve({ data: { ok: true, characters: [{
    id: 'char-1',
    name: '林岚',
    role_type: 'protagonist',
    gender: 'female',
    personality: '冷静',
    appearance_desc: '短发',
    outfit_desc: '白色外套',
    avatar_front_url: '',
    avatar_side_url: '',
    avatar_threequarter_url: '',
    avatar_fullbody_url: '',
  }] } })),
  createCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  autoGenerateCharacters: vi.fn(),
  updateCharacter: mocks.updateCharacter,
  deleteCharacter: mocks.deleteCharacter,
  aiRewriteCharacter: vi.fn(() => Promise.resolve({ data: { ok: true, candidate: { name: '林岚', personality: '坚定' } } })),
  generateCharacterReferences: mocks.generateCharacterReferences,
}))

vi.mock('../api/referenceData.js', () => ({
  listItems: vi.fn(() => Promise.resolve({ data: { ok: true, items: [{ value: 'protagonist', label: '主角' }] } })),
}))

describe('CharactersPage management', () => {
  beforeEach(() => {
    mocks.updateCharacter.mockClear()
    mocks.deleteCharacter.mockClear()
    mocks.generateCharacterReferences.mockClear()
  })

  it('opens detail drawer and saves edits', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage)
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    await wrapper.find('[data-test="character-name-input"]').setValue('林岚新版')
    await wrapper.find('[data-test="save-character"]').trigger('click')
    await flushPromises()

    expect(mocks.updateCharacter).toHaveBeenCalledWith('char-1', expect.objectContaining({ name: '林岚新版' }))
  })

  it('regenerates one reference image slot', async () => {
    const CharactersPage = (await import('../views/CharactersPage.vue')).default
    const wrapper = mount(CharactersPage)
    await flushPromises()

    await wrapper.find('[data-test="character-card-char-1"]').trigger('click')
    await wrapper.find('[data-test="regenerate-avatar_front_url"]').trigger('click')
    await flushPromises()

    expect(mocks.generateCharacterReferences).toHaveBeenCalledWith('char-1', { slot: 'avatar_front_url' })
  })
})
```

- [ ] **Step 2: Write failing scene page test**

Create `web/src/__tests__/scenes-management-page.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  updateScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  generateSceneReferences: vi.fn(() => Promise.resolve({ data: { ok: true, generated: { reference_wideshot_url: 'https://cdn.test/wide.png' } } })),
}))

vi.mock('../api/scenes.js', () => ({
  listScenes: vi.fn(() => Promise.resolve({ data: { ok: true, scenes: [{
    id: 'scene-1',
    name: '办公室',
    scene_type: 'indoor',
    location_desc: '玻璃办公室',
    lighting: 'day',
    mood: 'tense',
    reference_wideshot_url: '',
    reference_midshot_url: '',
    reference_aerial_url: '',
  }] } })),
  createScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  autoGenerateScenes: vi.fn(),
  updateScene: mocks.updateScene,
  deleteScene: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
  aiRewriteScene: vi.fn(() => Promise.resolve({ data: { ok: true, candidate: { name: '办公室', mood: 'mysterious' } } })),
  generateSceneReferences: mocks.generateSceneReferences,
}))

vi.mock('../api/referenceData.js', () => ({
  listItems: vi.fn(() => Promise.resolve({ data: { ok: true, items: [{ value: 'indoor', label: '室内' }] } })),
}))

describe('ScenesPage management', () => {
  beforeEach(() => {
    mocks.updateScene.mockClear()
    mocks.generateSceneReferences.mockClear()
  })

  it('opens detail drawer and saves edits', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage)
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    await wrapper.find('[data-test="scene-name-input"]').setValue('办公室新版')
    await wrapper.find('[data-test="save-scene"]').trigger('click')
    await flushPromises()

    expect(mocks.updateScene).toHaveBeenCalledWith('scene-1', expect.objectContaining({ name: '办公室新版' }))
  })

  it('regenerates one scene reference slot', async () => {
    const ScenesPage = (await import('../views/ScenesPage.vue')).default
    const wrapper = mount(ScenesPage)
    await flushPromises()

    await wrapper.find('[data-test="scene-card-scene-1"]').trigger('click')
    await wrapper.find('[data-test="regenerate-reference_wideshot_url"]').trigger('click')
    await flushPromises()

    expect(mocks.generateSceneReferences).toHaveBeenCalledWith('scene-1', { slot: 'reference_wideshot_url' })
  })
})
```

- [ ] **Step 3: Run page tests to verify they fail**

Run:

```powershell
cd web
npx vitest run src/__tests__/characters-management-page.test.js src/__tests__/scenes-management-page.test.js
```

Expected:

- FAIL because pages do not expose drawer controls and `data-test` hooks yet.

- [ ] **Step 4: Wire `CharactersPage.vue` drawer state and imports**

Modify `web/src/views/CharactersPage.vue` script imports:

```javascript
import AssetDetailDrawer from '../components/assets/AssetDetailDrawer.vue'
import ReferenceImageGallery from '../components/assets/ReferenceImageGallery.vue'
import AiRewriteConfirmDialog from '../components/assets/AiRewriteConfirmDialog.vue'
import DangerConfirmDialog from '../components/assets/DangerConfirmDialog.vue'
import {
  listCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  autoGenerateCharacters,
  aiRewriteCharacter,
  generateCharacterReferences,
} from '../api/characters.js'
```

Add state:

```javascript
const selectedCharacter = ref(null)
const editingCharacter = reactive({})
const referenceLoadingSlot = ref('')
const deleteDialogOpen = ref(false)
const rewriteDialogOpen = ref(false)
const rewriteCandidate = ref({})
const rewriteInstruction = ref('')

const characterReferenceSlots = computed(() => selectedCharacter.value ? [
  { key: 'avatar_front_url', label: '正面', url: selectedCharacter.value.avatar_front_url },
  { key: 'avatar_side_url', label: '侧面', url: selectedCharacter.value.avatar_side_url },
  { key: 'avatar_threequarter_url', label: '三分之四', url: selectedCharacter.value.avatar_threequarter_url },
  { key: 'avatar_fullbody_url', label: '全身', url: selectedCharacter.value.avatar_fullbody_url },
] : [])
```

Add methods:

```javascript
function openCharacter(character) {
  selectedCharacter.value = character
  Object.assign(editingCharacter, { ...character })
}

async function saveCharacter() {
  if (!selectedCharacter.value) return
  await updateCharacter(selectedCharacter.value.id, { ...editingCharacter })
  await load()
  selectedCharacter.value = characters.value.find(c => c.id === selectedCharacter.value.id) || null
}

async function regenerateCharacterReference(slot) {
  if (!selectedCharacter.value) return
  referenceLoadingSlot.value = slot
  try {
    await generateCharacterReferences(selectedCharacter.value.id, { slot })
    await load()
    selectedCharacter.value = characters.value.find(c => c.id === selectedCharacter.value.id) || null
  } finally {
    referenceLoadingSlot.value = ''
  }
}

async function replaceCharacterReference(slot, url) {
  if (!selectedCharacter.value) return
  await updateCharacter(selectedCharacter.value.id, { [slot]: url })
  await load()
  selectedCharacter.value = characters.value.find(c => c.id === selectedCharacter.value.id) || null
}

async function confirmDeleteCharacter() {
  if (!selectedCharacter.value) return
  await deleteCharacter(selectedCharacter.value.id)
  deleteDialogOpen.value = false
  selectedCharacter.value = null
  await load()
}
```

- [ ] **Step 5: Wire `CharactersPage.vue` template**

Add `data-test` to character cards:

```vue
:data-test="`character-card-${c.id}`"
@click="openCharacter(c)"
```

Add drawer after existing dialogs:

```vue
<AssetDetailDrawer
  :open="Boolean(selectedCharacter)"
  title="角色详情"
  :subtitle="selectedCharacter?.name || ''"
  @close="selectedCharacter = null"
>
  <div class="space-y-4">
    <input data-test="character-name-input" v-model="editingCharacter.name" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100" />
    <textarea v-model="editingCharacter.personality" rows="3" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100" />
    <textarea v-model="editingCharacter.appearance_desc" rows="3" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100" />
    <textarea v-model="editingCharacter.outfit_desc" rows="3" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100" />

    <ReferenceImageGallery
      title="角色参考图"
      :slots="characterReferenceSlots"
      :loading-slot="referenceLoadingSlot"
      @regenerate="regenerateCharacterReference"
      @replace-url="replaceCharacterReference"
    />
  </div>
  <template #footer>
    <div class="flex justify-between gap-2">
      <button class="rounded bg-rose-600 px-4 py-2 text-sm text-white" @click="deleteDialogOpen = true">删除/归档</button>
      <button data-test="save-character" class="rounded bg-emerald-600 px-4 py-2 text-sm text-white" @click="saveCharacter">保存</button>
    </div>
  </template>
</AssetDetailDrawer>

<DangerConfirmDialog
  :open="deleteDialogOpen"
  title="删除或归档角色"
  message="如果角色已被系列、分镜或生产记录引用，系统会归档而不是硬删除。"
  confirm-text="确认处理"
  @cancel="deleteDialogOpen = false"
  @confirm="confirmDeleteCharacter"
/>
```

- [ ] **Step 6: Apply the same drawer pattern to `ScenesPage.vue`**

Use these slot definitions:

```javascript
const sceneReferenceSlots = computed(() => selectedScene.value ? [
  { key: 'reference_wideshot_url', label: '广角', url: selectedScene.value.reference_wideshot_url },
  { key: 'reference_midshot_url', label: '中景', url: selectedScene.value.reference_midshot_url },
  { key: 'reference_aerial_url', label: '俯拍', url: selectedScene.value.reference_aerial_url },
] : [])
```

Use these API calls:

```javascript
await updateScene(selectedScene.value.id, { ...editingScene })
await generateSceneReferences(selectedScene.value.id, { slot })
await updateScene(selectedScene.value.id, { [slot]: url })
await deleteScene(selectedScene.value.id)
```

Add `data-test` hooks:

```vue
:data-test="`scene-card-${s.id}`"
data-test="scene-name-input"
data-test="save-scene"
```

- [ ] **Step 7: Run character and scene page tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/characters-management-page.test.js src/__tests__/scenes-management-page.test.js
```

Expected:

- PASS.

- [ ] **Step 8: Commit Task 6**

Run:

```powershell
git add web/src/views/CharactersPage.vue web/src/views/ScenesPage.vue web/src/__tests__/characters-management-page.test.js web/src/__tests__/scenes-management-page.test.js
git commit -m "feat: add character and scene management drawers"
```

Expected:

- Commit succeeds with only Task 6 files staged.

---

## Task 7: Series Detail Asset Management

**Files:**

- Modify: `web/src/views/SeriesDetailPage.vue`
- Modify: `web/src/api/series.js`
- Test: `web/src/__tests__/series-detail-video-production.test.js`

- [ ] **Step 1: Extend existing series detail test with edit and unlink expectations**

Modify `web/src/__tests__/series-detail-video-production.test.js` mocks:

```javascript
const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  updateSeries: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  unlinkCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  unlinkScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  autoPlanEpisode: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  createVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-1' } } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startEpisodeProduction: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-1' }, route: '/video-production/run-1' } })),
}))
```

Update `getSeries` mock series payload:

```javascript
characters: [{
  id: 'char-1',
  name: '林岚',
  role_type: 'protagonist',
  avatar_front_url: 'https://cdn.test/front.png',
}],
scenes: [{
  id: 'scene-1',
  name: '办公室',
  scene_type: 'indoor',
  reference_wideshot_url: 'https://cdn.test/wide.png',
}],
```

Update mocked API exports:

```javascript
updateSeries: mocks.updateSeries,
unlinkCharacter: mocks.unlinkCharacter,
unlinkScene: mocks.unlinkScene,
deleteSeries: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
```

Add tests:

```javascript
  it('updates series settings from detail page', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="edit-series"]').trigger('click')
    await wrapper.find('[data-test="series-title-input"]').setValue('New Title')
    await wrapper.find('[data-test="save-series"]').trigger('click')
    await flushPromises()

    expect(mocks.updateSeries).toHaveBeenCalledWith('sid', expect.objectContaining({ title: 'New Title' }))
  })

  it('unlinks character from series', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="unlink-character-char-1"]').trigger('click')
    await flushPromises()

    expect(mocks.unlinkCharacter).toHaveBeenCalledWith('sid', 'char-1')
  })
```

- [ ] **Step 2: Run series detail tests to verify they fail**

Run:

```powershell
cd web
npx vitest run src/__tests__/series-detail-video-production.test.js
```

Expected:

- FAIL because controls are missing.

- [ ] **Step 3: Add series settings edit UI and actions**

Modify `web/src/views/SeriesDetailPage.vue` imports:

```javascript
import { getSeries, autoGenerateAssets, getStyleLock, lockSeriesStyle, updateSeries, deleteSeries, unlinkCharacter, unlinkScene } from '../api/series.js'
import DangerConfirmDialog from '../components/assets/DangerConfirmDialog.vue'
import ReferenceImageGallery from '../components/assets/ReferenceImageGallery.vue'
```

Add state:

```javascript
const editingSeries = ref(false)
const seriesForm = reactive({ title: '', logline: '', genre: '', target_duration: 60, mode: 'step_by_step', pilot_first: true })
const deletingSeries = ref(false)

function beginEditSeries() {
  Object.assign(seriesForm, {
    title: series.value?.title || '',
    logline: series.value?.logline || '',
    genre: series.value?.genre || '',
    target_duration: series.value?.target_duration || 60,
    mode: series.value?.mode || 'step_by_step',
    pilot_first: series.value?.pilot_first ?? true,
  })
  editingSeries.value = true
}

async function saveSeries() {
  await updateSeries(route.params.id, { ...seriesForm })
  editingSeries.value = false
  await load()
}

async function removeCharacter(characterId) {
  await unlinkCharacter(route.params.id, characterId)
  await load()
}

async function removeScene(sceneId) {
  await unlinkScene(route.params.id, sceneId)
  await load()
}
```

Add template controls:

```vue
<button data-test="edit-series" @click="beginEditSeries" class="rounded bg-slate-700 px-3 py-2 text-sm text-white">
  编辑系列
</button>

<div v-if="editingSeries" class="mb-6 rounded-xl border border-slate-700 bg-slate-950/50 p-4">
  <input data-test="series-title-input" v-model="seriesForm.title" class="mb-3 w-full rounded bg-slate-900 px-3 py-2 text-slate-100" />
  <textarea v-model="seriesForm.logline" rows="3" class="mb-3 w-full rounded bg-slate-900 px-3 py-2 text-slate-100" />
  <button data-test="save-series" @click="saveSeries" class="rounded bg-emerald-600 px-4 py-2 text-sm text-white">保存系列</button>
</div>
```

Add linked asset sections:

```vue
<section class="mt-6 rounded-xl border border-slate-700 bg-slate-950/50 p-4">
  <h2 class="mb-3 text-lg font-semibold text-slate-100">关联角色</h2>
  <div v-for="character in series.characters || []" :key="character.id" class="mb-2 flex items-center justify-between rounded bg-slate-900/60 p-3">
    <div>
      <div class="text-sm text-slate-100">{{ character.name }}</div>
      <div class="text-xs text-slate-500">{{ character.role_type }}</div>
    </div>
    <button :data-test="`unlink-character-${character.id}`" class="rounded border border-slate-700 px-3 py-1 text-xs text-slate-300" @click="removeCharacter(character.id)">
      取消关联
    </button>
  </div>
</section>

<section class="mt-4 rounded-xl border border-slate-700 bg-slate-950/50 p-4">
  <h2 class="mb-3 text-lg font-semibold text-slate-100">关联场景</h2>
  <div v-for="scene in series.scenes || []" :key="scene.id" class="mb-2 flex items-center justify-between rounded bg-slate-900/60 p-3">
    <div>
      <div class="text-sm text-slate-100">{{ scene.name }}</div>
      <div class="text-xs text-slate-500">{{ scene.scene_type }}</div>
    </div>
    <button :data-test="`unlink-scene-${scene.id}`" class="rounded border border-slate-700 px-3 py-1 text-xs text-slate-300" @click="removeScene(scene.id)">
      取消关联
    </button>
  </div>
</section>
```

- [ ] **Step 4: Run series detail tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/series-detail-video-production.test.js
```

Expected:

- PASS.

- [ ] **Step 5: Commit Task 7**

Run:

```powershell
git add web/src/views/SeriesDetailPage.vue web/src/api/series.js web/src/__tests__/series-detail-video-production.test.js
git commit -m "feat: add series asset management controls"
```

Expected:

- Commit succeeds with only Task 7 files staged.

---

## Task 8: Review Center Transparency And Image Edit UI

**Files:**

- Modify: `web/src/views/AIVideoReviewPage.vue`
- Modify: `web/src/api/videoProduction.js`
- Test: `web/src/__tests__/ai-video-review-page.test.js`

- [ ] **Step 1: Extend review page test with reference evidence and image edit**

Modify `web/src/__tests__/ai-video-review-page.test.js` review item mock to include:

```javascript
reference_evidence: {
  reference_urls: ['https://cdn.test/front.png', 'https://cdn.test/wide.png'],
  character_reference_urls: ['https://cdn.test/front.png'],
  style_reference_urls: ['https://cdn.test/wide.png'],
  scene_id: 'scene-1',
  character_ids: ['char-1'],
},
```

Add mocked API:

```javascript
imageEditProductionAsset: vi.fn(() => Promise.resolve({ data: { ok: true, asset: { id: 'asset-2' } } })),
voidProductionAsset: vi.fn(() => Promise.resolve({ data: { ok: true } })),
```

Add test:

```javascript
it('shows reference evidence and submits image edit instruction', async () => {
  const AIVideoReviewPage = (await import('../views/AIVideoReviewPage.vue')).default
  const wrapper = mount(AIVideoReviewPage)
  await flushPromises()

  expect(wrapper.text()).toContain('参考图依据')
  expect(wrapper.html()).toContain('https://cdn.test/front.png')

  await wrapper.find('[data-test="open-image-edit"]').trigger('click')
  await wrapper.find('[data-test="image-edit-instruction"]').setValue('修正脸部一致性')
  await wrapper.find('[data-test="submit-image-edit"]').trigger('click')
  await flushPromises()

  const api = await import('../api/videoProduction.js')
  expect(api.imageEditProductionAsset).toHaveBeenCalledWith(expect.any(String), { instruction: '修正脸部一致性' })
})
```

- [ ] **Step 2: Run review page test to verify it fails**

Run:

```powershell
cd web
npx vitest run src/__tests__/ai-video-review-page.test.js
```

Expected:

- FAIL because reference evidence and image edit UI are missing.

- [ ] **Step 3: Add image edit and void imports/state**

Modify `web/src/views/AIVideoReviewPage.vue` imports:

```javascript
import {
  getVideoProductionRun,
  listReviewItems,
  reviewAsset,
  bulkReviewProductionAssets,
  retryAssetPersistence,
  startAssetRegeneration,
  syncAssetRegeneration,
  syncImageStage,
  runRealWorkerStep,
  imageEditProductionAsset,
  voidProductionAsset,
} from '../api/videoProduction.js'
```

Add state:

```javascript
const imageEditOpen = ref(false)
const imageEditInstruction = ref('')
```

Add methods:

```javascript
async function submitImageEdit() {
  if (!selected.value || !imageEditInstruction.value.trim()) return
  acting.value = true
  try {
    await imageEditProductionAsset(selected.value.id, { instruction: imageEditInstruction.value.trim() })
    imageEditOpen.value = false
    imageEditInstruction.value = ''
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.response?.data?.detail || e.message || '改图失败'
  } finally {
    acting.value = false
  }
}

async function voidCurrentAsset() {
  if (!selected.value) return
  const comment = prompt('作废原因：')
  if (comment === null) return
  acting.value = true
  try {
    await voidProductionAsset(selected.value.id, { comment })
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.response?.data?.detail || e.message || '作废失败'
  } finally {
    acting.value = false
  }
}
```

- [ ] **Step 4: Add reference evidence and image edit UI**

In selected asset details area, add:

```vue
<section class="rounded-lg border border-gray-700/50 bg-slate-950/40 p-3">
  <h3 class="mb-2 font-medium text-slate-200">参考图依据</h3>
  <div v-if="selected.reference_evidence?.reference_urls?.length" class="grid grid-cols-2 gap-2">
    <a
      v-for="url in selected.reference_evidence.reference_urls"
      :key="url"
      :href="url"
      target="_blank"
      class="block overflow-hidden rounded border border-slate-800 bg-slate-950"
    >
      <img :src="url" alt="参考图" class="h-24 w-full object-contain" />
      <div class="truncate px-2 py-1 text-xs text-slate-500">{{ url }}</div>
    </a>
  </div>
  <p v-else class="text-xs text-slate-500">当前素材没有记录参考图。</p>
</section>
```

In action buttons, add:

```vue
<button
  v-if="selected.asset_type === 'image'"
  data-test="open-image-edit"
  @click="imageEditOpen = true"
  :disabled="acting"
  class="cursor-pointer rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
>
  改图/重绘
</button>
<button
  @click="voidCurrentAsset"
  :disabled="acting"
  class="cursor-pointer rounded-lg border border-rose-700 px-4 py-2 text-sm text-rose-200 hover:bg-rose-950/40 disabled:opacity-50"
>
  作废当前版本
</button>
```

Add dialog:

```vue
<div v-if="imageEditOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="imageEditOpen = false">
  <section class="w-full max-w-lg rounded-lg border border-slate-800 bg-slate-950 p-5">
    <h2 class="text-lg font-semibold text-slate-100">改图/重绘</h2>
    <p class="mt-2 text-sm text-slate-400">系统会基于当前图片、分镜提示词和参考图生成新版本，不覆盖旧版本。</p>
    <textarea
      data-test="image-edit-instruction"
      v-model="imageEditInstruction"
      rows="4"
      class="mt-4 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
      placeholder="例如：保持发型和服装不变，修正脸部一致性"
    />
    <div class="mt-4 flex justify-end gap-2">
      <button class="rounded border border-slate-700 px-4 py-2 text-sm text-slate-300" @click="imageEditOpen = false">取消</button>
      <button data-test="submit-image-edit" class="rounded bg-indigo-600 px-4 py-2 text-sm text-white" @click="submitImageEdit">生成新版本</button>
    </div>
  </section>
</div>
```

- [ ] **Step 5: Run review page tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/ai-video-review-page.test.js
```

Expected:

- PASS.

- [ ] **Step 6: Commit Task 8**

Run:

```powershell
git add web/src/views/AIVideoReviewPage.vue web/src/api/videoProduction.js web/src/__tests__/ai-video-review-page.test.js
git commit -m "feat: expose review reference evidence and image edits"
```

Expected:

- Commit succeeds with only Task 8 files staged.

---

## Task 9: Regression And Full Verification

**Files:**

- No new files unless tests reveal a focused fix.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
pytest server/tests/test_asset_lifecycle_service.py server/tests/test_reference_asset_service.py server/tests/test_asset_ai_rewrite_service.py server/tests/test_review_asset_edit_service.py server/tests/test_series_api.py server/tests/test_series_style_lock_pipeline.py server/tests/test_video_production_api.py -q
```

Expected:

- PASS.

- [ ] **Step 2: Run full backend tests**

Run:

```powershell
pytest server/tests -q
```

Expected:

- PASS. Existing warnings are acceptable only if they match known SQLAlchemy reflection warnings already present before this work.

- [ ] **Step 3: Run focused frontend tests**

Run:

```powershell
cd web
npx vitest run src/__tests__/asset-detail-drawer.test.js src/__tests__/reference-image-gallery.test.js src/__tests__/characters-management-page.test.js src/__tests__/scenes-management-page.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js
```

Expected:

- PASS.

- [ ] **Step 4: Run full frontend tests**

Run:

```powershell
cd web
npx vitest run
```

Expected:

- PASS.

- [ ] **Step 5: Run text scan for English UI regressions in touched pages**

Run:

```powershell
rg -n "Delete|Archive|Regenerate|Edit image|Reference evidence|Save|Cancel|Close" web/src/views/CharactersPage.vue web/src/views/ScenesPage.vue web/src/views/SeriesDetailPage.vue web/src/views/AIVideoReviewPage.vue web/src/components/assets
```

Expected:

- No user-facing English labels remain in touched UI. English function names, CSS classes, API keys, and test names are acceptable.

- [ ] **Step 6: Run app smoke check**

Start or reuse local servers, then open the existing dev URL.

Backend:

```powershell
cd server
.\venv\Scripts\python.exe app\main.py
```

Frontend:

```powershell
cd web
npm run dev
```

Manual smoke:

- Open `http://localhost:3000`.
- Visit role assets page.
- Open a character drawer.
- Confirm reference image gallery is visible.
- Visit scene assets page.
- Open a scene drawer.
- Visit a series detail page.
- Confirm linked role/scene areas show.
- Visit review center with a run that has image review items.
- Confirm reference evidence and image edit entry are visible.

- [ ] **Step 7: Commit verification fixes if needed**

If Step 1-6 reveal fixes, commit only the focused files:

```powershell
git add <exact fixed files>
git commit -m "fix: stabilize asset management flow"
```

Expected:

- Commit includes only files changed for verification fixes.

---

## Self-Review

### Spec Coverage

- Series edit/delete/archive: Task 1 and Task 7.
- Character asset edit/delete/archive: Task 1 and Task 6.
- Scene asset edit/delete/archive: Task 1 and Task 6.
- Reference image viewing: Task 5, Task 6, Task 7, Task 8.
- Reference image regeneration: Task 2 and Task 6.
- AI rewrite candidates: Task 3 and Task 6.
- Review center reference evidence: Task 4 and Task 8.
- Image edit/redraw as new version: Task 4 and Task 8.
- Production asset void without physical delete: Task 4 and Task 8.
- Chinese UI labels: Task 9 scan.
- Existing one-click production regression: Task 9 focused and full tests.

### Placeholder Scan

This plan spells out concrete files, failing tests, implementation snippets, commands, and expected results.

### Type Consistency

- Backend error classes use `code`, `message`, and `details`.
- Frontend API functions match route paths in backend tasks.
- Reference image slot names match `Character` and `Scene` model fields.
- Review image edit preserves `run_id`, `episode_id`, `frame_id`, `asset_type`, `stage`, and version fields.

## Plan Design Review Addendum

**Initial design completeness:** 6/10.

The plan has the right screens and actions, but it was too implementation-heavy. A 10/10 plan specifies what users see first, how empty/error/partial states behave, how the same UI works on mobile, and which existing design primitives must be reused.

**Design system status:** No root `DESIGN.md` exists. Until a formal design system is created, use the existing app vocabulary observed in:

- `web/src/components/layout/PageContainer.vue`
- `web/src/components/ui/AppButton.vue`
- `web/src/components/ui/AppDialog.vue`
- `web/src/components/EmptyState.vue`
- `web/src/components/StatusBadge.vue`
- Current dark workbench pages: `CharactersPage.vue`, `ScenesPage.vue`, `SeriesDetailPage.vue`, `AIVideoReviewPage.vue`

### Information Architecture

**Score:** 6/10 -> 9/10 after this addendum.

Primary rule: every screen exposes three layers only: orientation, active work, and contextual action. Do not stack more panels just because new functions exist.

```text
Characters / Scenes
+-------------------------------------------------------------+
| Page title + two primary actions                            |
| Filters / readiness summary                                 |
+-------------------------------+-----------------------------+
| Asset list or compact grid    | Detail drawer               |
| name, type, reference status  | editable fields             |
| selected state                | reference gallery           |
| empty state with create action| AI rewrite + delete footer  |
+-------------------------------+-----------------------------+
```

```text
Series Detail
+-------------------------------------------------------------+
| Back link + title + style lock + start production           |
+-------------------------------------------------------------+
| Series settings and reference readiness summary             |
+-------------------------------+-----------------------------+
| Episodes / production runs    | Linked characters / scenes  |
|                               | reference image entry       |
+-------------------------------+-----------------------------+
```

```text
Review Center
+-------------------------------------------------------------+
| Gate tabs + run status + refresh/sync                       |
+---------------+------------------------------+--------------+
| Review queue  | Asset preview                | Evidence     |
| version/state | storyboard + audit results   | ref images   |
| selection     | action bar                   | edit history |
+---------------+------------------------------+--------------+
```

The three most important things visible above the fold:

- Characters/Scenes: asset identity, reference image completeness, and the next available action.
- Series Detail: style-lock readiness, next episode action, and linked asset health.
- Review Center: current asset preview, gate-blocking reason, and approve/reject/edit actions.

### Interaction State Coverage

**Score:** 5/10 -> 9/10 after this addendum.

| Feature | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Character/scene list | Skeleton rows or muted loading line in the content area | `EmptyState` with "暂无角色资产/暂无场景资产" and primary create action | Inline red error with retry button, keep existing data if available | Toast or inline "已保存" for 2 seconds, drawer remains open | Show reference completeness count and "待生成" slot badges |
| Detail drawer | Drawer opens immediately with disabled controls until data is ready | Not applicable; close drawer if selected asset no longer exists | Error banner at top of drawer, preserve unsaved form draft | Save button returns to normal, updated fields remain visible | AI rewrite candidate may fill only changed fields; unchanged fields stay visible |
| Reference gallery | Slot-level spinner only on the requested slot | Each empty slot shows label, "待生成", and one regenerate button | Failed slot shows "生成失败" and retry; other slots remain usable | New image appears in the same slot with timestamp metadata if present | Some slots may be ready and some missing; never block the whole drawer |
| Series linked assets | Compact loading row below settings | "尚未关联角色/场景" with add-link action | 409 conflict shows affected series/run count and safe alternative | Unlink removes row without page jump | Archived assets show read-only badge and are hidden from add picker |
| Review queue | Queue skeleton, preview panel disabled | "暂无需要人工审查的素材" and link back to production monitor | Stale version or provider error appears above action bar with repair action | Approved item leaves queue or changes state without losing selection context | Reference evidence may be incomplete; show missing role/scene refs explicitly |
| Image edit dialog | Submit button shows "生成中", source preview remains visible | Not applicable; dialog opens only from image asset | Failure keeps instruction text and source image visible | New version is selected and old version remains reachable through history | Provider can return pending; show "生成任务已提交，等待同步" instead of pretending completion |

### User Journey And Trust

**Score:** 6/10 -> 9/10 after this addendum.

| Step | User does | User should feel | Plan support |
|---|---|---|---|
| 1 | Opens character/scene page | "I can see what is production-ready." | Readiness counts and reference badges are visible before editing. |
| 2 | Opens a drawer | "This is the same asset, not a separate editor." | Drawer keeps page context visible and uses the selected state. |
| 3 | Regenerates one reference image | "Only this slot will change." | Slot label, slot-level spinner, and slot-level success/error states. |
| 4 | Uses AI rewrite | "I can review before overwriting." | Before/after candidate dialog, no auto-save. |
| 5 | Reviews a production asset | "I know why this asset exists and what references it used." | Evidence panel groups storyboard, character refs, scene refs, and audit. |
| 6 | Edits/rejects/voids | "I am not breaking the audit trail." | Copy says "作废当前版本", version badges remain visible. |

### AI-Slop And Visual Specificity

**Score:** 6/10 -> 9/10 after this addendum.

Use app UI rules, not landing-page rules:

- No hero sections, no marketing copy, no decorative gradient blobs.
- Avoid purple as the dominant action color. Use cyan for creation/generation, emerald for pass/save, amber for pending/sync, red/rose for destructive actions, slate for secondary actions.
- Cards are allowed only for asset tiles or repeated queue rows. Do not put cards inside cards.
- Keep panel radii at 8px unless reusing an existing component that already uses a larger radius.
- Use utility copy: "正面参考图待生成", "作废当前版本", "当前版本已过期". Do not add explanatory paragraphs inside the work surface.
- Do not rely on hover to reveal primary actions; mobile has no hover.

### Responsive And Accessibility

**Score:** 4/10 -> 9/10 after this addendum.

Breakpoints:

- `>=1280px`: list/grid plus right drawer can coexist; review center uses queue, preview, evidence columns.
- `768px-1279px`: drawer overlays content at max 720px; review center uses queue plus preview, evidence collapses below preview.
- `<768px`: one-column layout; drawer becomes full-screen; reference images use two columns when width allows and one column below 420px; review queue and detail become tabbed sections.

Accessibility rules:

- Every form control has a visible `<label>` or `aria-label`; placeholder text is never the only label.
- Drawer traps focus, closes on Escape, and returns focus to the asset card that opened it.
- Modal dialogs use `role="dialog"` through `AppDialog` or Headless UI semantics.
- Action buttons have minimum 44px touch target height on mobile.
- All status color changes also include text labels.
- Reference thumbnails have meaningful alt text: "林岚 正面参考图", "办公室 广角参考图".
- Keyboard order: list item -> edit fields -> reference actions -> footer actions. Destructive action is last in the tab order.
- Body text contrast must meet 4.5:1; disabled buttons must still show readable labels.

### Design Decisions Resolved

| Decision | Resolution | Reason |
|---|---|---|
| Drawer vs full page editor | Use drawer on desktop/tablet, full-screen drawer on mobile | Preserves list context while keeping mobile usable. |
| Reference image placement | Put reference gallery inside asset drawer and evidence panel | References are not separate media-library items; they explain asset readiness. |
| Review center action naming | Use "作废当前版本", never "删除素材" | Keeps audit-chain expectations clear. |
| AI rewrite persistence | Candidate review first, user saves after confirmation | Prevents AI from overwriting manual asset edits. |
| Component styling | Reuse existing UI primitives and dark workbench vocabulary | Avoids creating a second design system. |

### Design Decisions Deferred

| Deferred | Rationale |
|---|---|
| Full project `DESIGN.md` | Useful, but larger than this asset-management slice. Run `design-consultation` later if the product needs a formal system. |
| Visual PNG mockups | gstack designer binary exists, but no OpenAI API key is configured for it in this environment. |
| Dedicated image comparison mode | First version only needs large preview and reference evidence; side-by-side diff can come after real edit usage. |

### NOT In Scope

- No visual timeline editor.
- No separate media-library product.
- No marketing/landing redesign.
- No new navigation concept beyond existing dy_auto admin navigation.
- No physical deletion UI for production review assets.

### Design Review Scorecard

| Pass | Before | After | Result |
|---|---:|---:|---|
| Information architecture | 6/10 | 9/10 | Added hierarchy diagrams and above-fold priorities. |
| Interaction states | 5/10 | 9/10 | Added loading, empty, error, success, and partial-state table. |
| User journey | 6/10 | 9/10 | Added trust-focused journey storyboard. |
| AI-slop risk | 6/10 | 9/10 | Added app UI rules and anti-pattern constraints. |
| Design system alignment | 5/10 | 8/10 | No `DESIGN.md`, but existing primitives are now named. |
| Responsive/accessibility | 4/10 | 9/10 | Added breakpoint behavior and accessibility rules. |
| Unresolved decisions | 5/10 | 9/10 | Resolved the implementer-facing design choices; deferred only larger design-system work. |

**Overall design score:** 6/10 -> 9/10.

## Plan Eng Review Addendum

**Review mode:** FULL_REVIEW. Scope accepted with guardrails. This is not a cosmetic UI task: the feature crosses existing asset lifecycle, provider task lifecycle, review gates, and frontend management surfaces. The plan should not be reduced to frontend-only CRUD because that would leave the review center unable to preserve audit/version history.

**Engineering status:** 7/10 before this addendum, 9/10 after the required corrections below. The remaining 1 point depends on implementation-time verification against real configured providers.

### Architecture Findings

1. **P1: Image edit was specified as a synchronous happy path, but existing image creation is asynchronous.** `create_image_task` may return `queued` with no provider task id, or `running` before assets exist. The implementation must return a clear pending/queued response or add a sync endpoint; it must not call `dispatch_queued_image_task` unconditionally and must not read `task.assets`, because `ImageCreationTask` has no SQLAlchemy relationship named `assets`.

2. **P1: New review asset versions need stale-version and double-submit protection.** `VideoProductionAsset` has a unique `(run_id, frame_id, asset_type, version)` constraint. `edit_image_asset` must re-read the current latest asset inside the transaction before creating the new version, reject stale source versions with `STALE_ASSET_VERSION`, and demote older latest rows only after the replacement asset is flushed successfully.

3. **P2: Character/scene archive visibility needs an explicit API contract.** The plan says archived records are hidden unless requested, but the current list endpoints have no `include_archived` query parameter. Add `include_archived: bool = Query(False)` to character and scene list routes and tests for both default and explicit archive visibility.

4. **P2: Reference generation must use capability-aware model resolution.** The first draft used `get_model_for_scene`, which only filters model type/scene. The service must use `resolve_image_model_for_capability(db, "image_generation", "text_to_image")` so Seedream/Pixelle capability configuration is honored.

5. **P2: Response shapes need to be deliberate.** Existing endpoints can keep legacy response shapes, but every new endpoint in this plan should include `ok`, `warnings`, and `missing_requirements` at the top level. Tests should assert those fields for create/edit/regenerate/void actions.

### Required Implementation Rules

- `POST /api/video-production/assets/{asset_id}/image-edit` may return a new asset only when an `ImageCreationAsset` exists. If the provider task is queued or running, return a pending payload with `image_creation_task_id`, `status`, and a Chinese user-facing message, then let the UI refresh/sync.
- Add either `POST /api/video-production/assets/{asset_id}/image-edit/sync` or reuse an existing image-task sync path that can convert a completed `ImageCreationAsset` into a new `VideoProductionAsset` version.
- Add `expected_version` to void and image-edit request bodies or validate the source asset is still the latest at write time. If the UI submits an old version, return `STALE_ASSET_VERSION` and reload the current latest asset.
- Do not physically delete review-center assets. Void changes status and records a `VideoReviewRecord`; edit creates a new version and preserves the old row.
- Lifecycle JSON scans are acceptable for this management slice, but must be isolated inside `asset_lifecycle_service.py` and treated as a v1 fallback. Do not spread ad hoc JSON traversal across route files.

### What Already Exists

| Existing code | Reuse decision |
|---|---|
| `server/app/services/image_creation_service.py` | Reuse for image edit provider dispatch, capability checks, cost confirmation, provider options, and persistence. Do not duplicate provider calls in `review_asset_edit_service.py`. |
| `server/app/services/runtime_model_config.py::resolve_image_model_for_capability` | Reuse for reference image generation and image edit capability checks. |
| `server/app/services/video_production_service.py::_demote_latest_assets` and version helpers | Reuse or mirror the same version semantics for review edit replacements. |
| `server/app/routers/video_production.py::_asset_payload` | Extend with `reference_evidence`; do not create a second payload contract for review items. |
| `web/src/components/ui/AppDialog.vue`, `AppButton.vue`, `StatusBadge.vue`, `EmptyState.vue` | Reuse for drawers/dialogs/buttons/status; avoid a second asset-management design system. |

### NOT In Scope

- No timeline editor or shot-by-shot visual editor.
- No separate media library product.
- No provider-specific Seedream-only UI in this slice; provider-specific options stay in the model/image configuration surfaces.
- No physical deletion of production review assets.
- No rewrite of the long-video scheduler or production worker in this plan.

### Data Flow

```text
+-------------------+      +-------------------------+      +----------------------+
| Character/Scene   | ---> | reference_asset_service | ---> | configured image     |
| drawer action     |      | slot validation + meta  |      | provider capability  |
+-------------------+      +-------------------------+      +----------------------+
          |                           |
          v                           v
   URL slot updated          meta_json.reference_generation
```

```text
+------------------+      +---------------------------+      +--------------------+
| Review image edit | ---> | image_creation_service    | ---> | ImageCreationTask  |
| current version   |      | image_to_image capability |      | queued/running/done |
+------------------+      +---------------------------+      +--------------------+
          |                                                       |
          | done                                                  | pending
          v                                                       v
+-------------------------+                          +--------------------------+
| new VideoProductionAsset |                          | UI shows pending/sync    |
| version + old demoted    |                          | without breaking gate    |
+-------------------------+                          +--------------------------+
```

### Test Coverage Diagram

```text
Lifecycle guards
  -> safe delete/archive service tests
  -> series/character/scene API tests

Reference generation
  -> slot validation tests
  -> model capability missing tests
  -> metadata and URL-field update tests

AI rewrite
  -> candidate-only service tests
  -> before/after confirm UI tests

Review edit and void
  -> void audit record tests
  -> image edit pending/running/done tests
  -> stale version and double-submit tests
  -> review item reference evidence API tests

Frontend management
  -> drawer/gallery/dialog component tests
  -> character/scene/series page tests
  -> review center edit/void/evidence tests
```

### Failure Modes

| Codepath | Production failure | Test required | User-visible handling |
|---|---|---|---|
| Reference image generation | No model supports `image_generation/text_to_image` | `MODEL_SCENE_NOT_CONFIGURED` API test | Chinese repair message points to model config |
| Character/scene archive | Referenced asset is hard-deleted accidentally | referenced storyboard/story_bible tests | API returns archived action and dependencies |
| Image edit submit | Task is queued and has no provider id | pending/queued service and API test | UI shows pending sync state, not failure |
| Image edit versioning | Two edits compute the same next version | stale/double-submit test | Second request returns conflict with latest asset id |
| Review void | User voids an old version | stale version API test | UI reloads latest version and explains conflict |
| Reference evidence payload | Review item has no storyboard frame | payload test with missing frame | Evidence panel shows missing refs, not blank crash |

No critical silent gaps remain after these corrections.

### Performance Review

- Lifecycle dependency checks may scan JSON fields. That is acceptable for the first management loop, but the service must narrow candidate rows where possible, and tests should include a modest multi-episode fixture so the query path is not accidentally quadratic in frontend usage.
- Review item payload extension should use the existing `run` already loaded by `review_items`; do not add per-asset run queries.
- Reference thumbnail galleries should lazy-load images and never block opening the drawer on image fetch completion.

### Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| Backend lifecycle | `server/app/services`, `server/app/routers`, `server/tests` | none |
| Backend reference + AI rewrite | `server/app/services`, `server/app/routers`, `server/tests` | none, but shares service/router modules |
| Backend review edit/void | `server/app/services`, `server/app/routers`, `server/tests` | none, but shares service/router modules |
| Frontend shared components | `web/src/components`, `web/src/__tests__` | backend API names stable |
| Frontend pages | `web/src/views`, `web/src/api`, `web/src/__tests__` | shared components and backend API names |

Parallel lanes:

- Lane A: Backend lifecycle -> backend reference/AI rewrite -> backend review edit/void. Keep sequential because they touch shared routers/services and error contracts.
- Lane B: Frontend shared components can run in parallel after API names are fixed.
- Lane C: Frontend pages waits for Lane B and backend route contract.

Execution order: start Lane A and Lane B in separate worktrees only after the route names in this plan are frozen. Merge Lane B, then implement Lane C against the final component API. Avoid parallel edits to `web/src/views/AIVideoReviewPage.vue` and `server/app/routers/video_production.py`.

### Completion Summary

- Step 0: Scope Challenge -> scope accepted with provider/version guardrails.
- Architecture Review: 5 issues found, all folded into this plan.
- Code Quality Review: 3 concrete corrections added: capability resolver, async image task handling, archive list contract.
- Test Review: coverage diagram produced, 6 required failure-mode tests added.
- Performance Review: 2 issues found, both scoped to lifecycle JSON scans and review payload query discipline.
- NOT in scope: written.
- What already exists: written.
- TODOS.md updates: 0 items proposed; all findings are required for this implementation and should not be deferred.
- Failure modes: 0 critical silent gaps after corrections.
- Outside voice: skipped; this is plan-stage local review and existing reviewer stack has already covered product/design.
- Parallelization: 3 lanes, 2 can start in parallel after API contract freeze, backend lane remains sequential.
- Lake Score: 9/10, complete option chosen for audit/version/provider correctness.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-06-01-series-assets-review-management.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, faster iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run in this pass | Earlier scope is accepted; no new CEO decision required. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not run in this pass | Not required before implementation plan repair. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 8 issues found, 0 critical gaps after plan corrections. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | Design addendum already raised plan from 6/10 to 9/10. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | Not required for this user-facing management slice. |

- **UNRESOLVED:** 0.
- **VERDICT:** ENG + DESIGN CLEARED. Ready to implement with `subagent-driven-development` or `executing-plans`.
