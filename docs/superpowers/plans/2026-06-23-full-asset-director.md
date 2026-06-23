# Full Asset Director Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full asset director stage that creates, reuses, classifies, and binds per-episode characters and scenes before real video production.

**Architecture:** Add a focused `asset_director_service` inside the AI video series domain. It owns director-plan normalization, deterministic asset matching, asset creation, metadata tagging, AI text artifact storage, and storyboard frame binding. Production start calls this service when prepared text artifacts are required; UI reads the same episode asset scope payload it already uses.

**Tech Stack:** FastAPI backend, SQLAlchemy ORM, pytest, Vue 3, Vitest.

---

## File Structure

- Create `server/app/domains/ai_video_series/asset_director_service.py`
  - Owns asset director constants, error type, plan application, LLM plan generation wrapper, and `ensure_asset_director_plan_for_episode`.
- Modify `server/app/domains/video_production/production_run_service.py`
  - Calls asset director after script/storyboard draft exists and before final episode scope validation.
- Modify `server/app/domains/ai_video_series/read_models.py`
  - Adds asset metadata classification fields to episode asset payloads.
- Modify `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`
  - Includes `asset_director_plan` as a series-run artifact for consumption binding.
- Modify `web/src/views/SeriesDetailPage.vue`
  - Displays asset classification badges for episode characters/scenes.
- Test `server/tests/test_asset_director_service.py`
  - Unit/integration coverage for matching, creation, metadata, and frame binding.
- Test `server/tests/test_video_production_start_flow_contract.py`
  - Production-start gate coverage.
- Test `web/src/__tests__/series-detail-agency.test.js`
  - UI badge display coverage.

---

### Task 1: Asset Director Service Contract Tests

**Files:**
- Create: `server/tests/test_asset_director_service.py`

- [ ] **Step 1: Write failing tests for asset creation, reuse, metadata, and frame binding**

Create `server/tests/test_asset_director_service.py`:

```python
import pytest

from app.db.models import AITextArtifact, Character, Episode, Scene, Series


def _series_with_episode(db):
    series = Series(title="Asset Show", logline="A doctor solves one mystery per episode.", total_episodes=2, status="draft")
    db.add(series)
    db.flush()
    ep1 = Episode(
        series_id=series.id,
        episode_number=1,
        title="Clinic Debt",
        status="pending",
        storyboard_json={"frames": [{"frame_id": "frame-001", "scene_number": 1}]},
    )
    ep2 = Episode(
        series_id=series.id,
        episode_number=2,
        title="Night Call",
        status="pending",
        storyboard_json={"frames": [{"frame_id": "frame-002", "scene_number": 1}]},
    )
    db.add_all([ep1, ep2])
    db.commit()
    return series, ep1, ep2


def test_apply_asset_director_plan_creates_episode_assets_and_tags_metadata(db):
    from app.domains.ai_video_series.asset_director_service import apply_asset_director_plan

    series, ep1, _ep2 = _series_with_episode(db)
    plan = {
        "series_id": series.id,
        "recurring_characters": [],
        "episode_assets": [{
            "episode_number": 1,
            "characters": [{
                "stable_key": "patient_ep1",
                "name": "Patient Wu",
                "asset_scope": "episode_only",
                "appearance_desc": "Thin patient with tired eyes.",
                "outfit_desc": "Gray hoodie.",
                "usage": "Triggers the debt reveal.",
            }],
            "scenes": [{
                "stable_key": "clinic_room_ep1",
                "name": "Clinic Room 3",
                "asset_scope": "episode_only",
                "scene_type": "indoor",
                "location_desc": "Small clinic room with medicine cabinet.",
                "lighting": "cold_fluorescent",
                "mood": "tense",
                "usage": "Main confrontation room.",
            }],
            "frame_bindings": [{
                "frame_id": "frame-001",
                "scene_stable_key": "clinic_room_ep1",
                "character_stable_keys": ["patient_ep1"],
            }],
        }],
    }

    result = apply_asset_director_plan(db, series.id, plan)
    db.refresh(ep1)

    character = db.query(Character).filter(Character.name == "Patient Wu").one()
    scene = db.query(Scene).filter(Scene.name == "Clinic Room 3").one()
    artifact = db.query(AITextArtifact).filter(AITextArtifact.artifact_type == "asset_director_plan").one()

    assert result["created_character_ids"] == [character.id]
    assert result["created_scene_ids"] == [scene.id]
    assert character.meta_json["series_id"] == series.id
    assert character.meta_json["episode_id"] == ep1.id
    assert character.meta_json["asset_scope"] == "episode_only"
    assert character.meta_json["asset_source"] == "asset_director"
    assert scene.meta_json["series_id"] == series.id
    assert scene.meta_json["episode_id"] == ep1.id
    assert scene.meta_json["asset_scope"] == "episode_only"
    assert artifact.status == "approved"
    frame = ep1.storyboard_json["frames"][0]
    assert frame["scene_id"] == scene.id
    assert frame["character_ids"] == [character.id]


def test_apply_asset_director_plan_reuses_recurring_character_across_episodes(db):
    from app.domains.ai_video_series.asset_director_service import apply_asset_director_plan

    series, ep1, ep2 = _series_with_episode(db)
    lead = Character(name="Dr Lin", role_type="protagonist", gender="female", meta_json={"asset_stable_key": "dr_lin"})
    db.add(lead)
    series.characters.append(lead)
    db.commit()

    plan = {
        "series_id": series.id,
        "recurring_characters": [{
            "stable_key": "dr_lin",
            "name": "Dr Lin",
            "reuse_character_id": lead.id,
            "asset_scope": "series_recurring",
            "episode_numbers": [1, 2],
            "appearance_desc": "Calm doctor with short hair.",
            "outfit_desc": "White coat.",
            "usage": "Series lead.",
        }],
        "episode_assets": [
            {"episode_number": 1, "characters": [], "scenes": [], "frame_bindings": [{"frame_id": "frame-001", "character_stable_keys": ["dr_lin"]}]},
            {"episode_number": 2, "characters": [], "scenes": [], "frame_bindings": [{"frame_id": "frame-002", "character_stable_keys": ["dr_lin"]}]},
        ],
    }

    result = apply_asset_director_plan(db, series.id, plan)
    db.refresh(ep1)
    db.refresh(ep2)

    assert result["reused_character_ids"] == [lead.id]
    assert db.query(Character).filter(Character.name == "Dr Lin").count() == 1
    assert ep1.storyboard_json["frames"][0]["character_ids"] == [lead.id]
    assert ep2.storyboard_json["frames"][0]["character_ids"] == [lead.id]
    assert lead.meta_json["asset_scope"] == "series_recurring"
    assert lead.meta_json["series_id"] == series.id


def test_apply_asset_director_plan_fails_on_ambiguous_name_match(db):
    from app.domains.ai_video_series.asset_director_service import AssetDirectorError, apply_asset_director_plan

    series, _ep1, _ep2 = _series_with_episode(db)
    first = Character(name="Nurse Chen", role_type="supporting", gender="female")
    second = Character(name="Nurse Chen", role_type="supporting", gender="female")
    db.add_all([first, second])
    series.characters.extend([first, second])
    db.commit()

    plan = {
        "series_id": series.id,
        "recurring_characters": [],
        "episode_assets": [{
            "episode_number": 1,
            "characters": [{"stable_key": "nurse", "name": "Nurse Chen", "asset_scope": "episode_only"}],
            "scenes": [],
            "frame_bindings": [],
        }],
    }

    with pytest.raises(AssetDirectorError) as exc:
        apply_asset_director_plan(db, series.id, plan)

    assert exc.value.code == "AMBIGUOUS_ASSET_MATCH"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import error for `asset_director_service`.

- [ ] **Step 3: Commit failing tests**

```powershell
git add server/tests/test_asset_director_service.py
git commit -m "test: define full asset director contract"
```

---

### Task 2: Implement Asset Director Service

**Files:**
- Create: `server/app/domains/ai_video_series/asset_director_service.py`

- [ ] **Step 1: Add service implementation**

Create `server/app/domains/ai_video_series/asset_director_service.py`:

```python
"""Full asset director service for multi-episode series assets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import AITextArtifact, Character, Episode, Scene, Series
from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
from app.domains.model_configuration.ai_generator import ai_generator


ASSET_DIRECTOR_ARTIFACT_TYPE = "asset_director_plan"
ASSET_DIRECTOR_SOURCE = "asset_director"
ASSET_SCOPES = {"series_recurring", "episode_only", "guest", "location_recurring"}
CHARACTER_KEYS = ("recurring_characters", "characters")


@dataclass
class AssetDirectorError(ValueError):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def apply_asset_director_plan(db: Session, series_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise AssetDirectorError("SERIES_NOT_FOUND", "Series not found.", {"series_id": series_id})
    if plan.get("series_id") not in (None, series_id):
        raise AssetDirectorError("PLAN_SERIES_MISMATCH", "Asset director plan belongs to another series.", {"series_id": series_id})

    episodes = {
        int(row.episode_number): row
        for row in db.query(Episode).filter(Episode.series_id == series_id).all()
    }
    stable_characters: dict[str, Character] = {}
    stable_scenes: dict[str, Scene] = {}
    created_character_ids: list[str] = []
    created_scene_ids: list[str] = []
    reused_character_ids: list[str] = []
    reused_scene_ids: list[str] = []

    for spec in plan.get("recurring_characters") or []:
        character, created = _resolve_character(db, series, None, spec)
        stable_characters[_stable_key(spec)] = character
        _append_once(created_character_ids if created else reused_character_ids, character.id)

    for episode_row in plan.get("episode_assets") or []:
        episode_number = int(episode_row.get("episode_number") or 0)
        episode = episodes.get(episode_number)
        if not episode:
            raise AssetDirectorError("EPISODE_NOT_FOUND", "Asset director plan references a missing episode.", {"episode_number": episode_number})

        for spec in episode_row.get("characters") or []:
            character, created = _resolve_character(db, series, episode, spec)
            stable_characters[_stable_key(spec)] = character
            _append_once(created_character_ids if created else reused_character_ids, character.id)

        for spec in episode_row.get("scenes") or []:
            scene, created = _resolve_scene(db, series, episode, spec)
            stable_scenes[_stable_key(spec)] = scene
            _append_once(created_scene_ids if created else reused_scene_ids, scene.id)

        if isinstance(episode.storyboard_json, dict):
            episode.storyboard_json = _bind_frames(episode.storyboard_json, episode_row.get("frame_bindings") or [], stable_characters, stable_scenes)
            flag_modified(episode, "storyboard_json")
        _write_script_scope(episode, episode_row, stable_characters, stable_scenes)

    db.flush()
    service = AITextArtifactService(db)
    artifact = service.create_artifact(
        series_id=series.id,
        target_type="series",
        target_id=series.id,
        artifact_type=ASSET_DIRECTOR_ARTIFACT_TYPE,
        source_type=ASSET_DIRECTOR_SOURCE,
        input_json={"source": "apply_asset_director_plan"},
        content_json=plan,
        content_text=json.dumps(plan, ensure_ascii=False),
        model_trace_json={"source": ASSET_DIRECTOR_SOURCE, "stage": ASSET_DIRECTOR_ARTIFACT_TYPE},
        created_by="system",
        commit=False,
    )
    service.approve_artifact(artifact.id, actor_user_id="system", commit=False)
    db.commit()
    return {
        "ok": True,
        "artifact_id": artifact.id,
        "created_character_ids": created_character_ids,
        "created_scene_ids": created_scene_ids,
        "reused_character_ids": reused_character_ids,
        "reused_scene_ids": reused_scene_ids,
    }


async def ensure_asset_director_plan_for_episode(db: Session, series_id: str, episode_id: str) -> dict[str, Any]:
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise AssetDirectorError("SERIES_NOT_FOUND", "Series not found.", {"series_id": series_id})
    episode = db.query(Episode).filter(Episode.id == episode_id, Episode.series_id == series_id).first()
    if not episode:
        raise AssetDirectorError("EPISODE_NOT_FOUND", "Episode not found.", {"episode_id": episode_id})

    service = AITextArtifactService(db)
    existing = service.latest_approved(target_type="series", target_id=series_id, artifact_type=ASSET_DIRECTOR_ARTIFACT_TYPE)
    if existing:
        return {"ok": True, "artifact_id": existing.id, "status": "preserved"}

    raw = await ai_generator.generate_custom(
        db,
        _director_system_prompt(),
        _director_user_prompt(series, episode),
        max_tokens=8192,
        temperature=0.2,
    )
    plan = _parse_json(str(raw or ""))
    return apply_asset_director_plan(db, series_id, plan)


def _resolve_character(db: Session, series: Series, episode: Episode | None, spec: dict[str, Any]) -> tuple[Character, bool]:
    existing = _find_character(db, series, spec)
    if existing:
        _merge_asset_meta(existing, series, episode, spec)
        return existing, False
    character = Character(
        name=str(spec.get("name") or "").strip(),
        role_type=str(spec.get("role_type") or "supporting")[:20],
        gender=str(spec.get("gender") or "unknown")[:10],
        age_range=str(spec.get("age_range") or "")[:20],
        personality=str(spec.get("personality") or ""),
        appearance_desc=str(spec.get("appearance_desc") or ""),
        outfit_desc=str(spec.get("outfit_desc") or ""),
        meta_json=_asset_meta(series, episode, spec),
    )
    db.add(character)
    series.characters.append(character)
    db.flush()
    return character, True


def _resolve_scene(db: Session, series: Series, episode: Episode | None, spec: dict[str, Any]) -> tuple[Scene, bool]:
    existing = _find_scene(db, series, spec)
    if existing:
        _merge_asset_meta(existing, series, episode, spec)
        return existing, False
    scene = Scene(
        name=str(spec.get("name") or "").strip(),
        scene_type=str(spec.get("scene_type") or "indoor")[:20],
        location_desc=str(spec.get("location_desc") or ""),
        lighting=str(spec.get("lighting") or "")[:50],
        mood=str(spec.get("mood") or "")[:50],
        meta_json=_asset_meta(series, episode, spec),
    )
    db.add(scene)
    series.scenes.append(scene)
    db.flush()
    return scene, True


def _find_character(db: Session, series: Series, spec: dict[str, Any]) -> Character | None:
    reuse_id = spec.get("reuse_character_id")
    if reuse_id:
        return _linked_character_or_error(series, str(reuse_id))
    return _find_linked_by_name_or_key(series.characters or [], spec, "Character")


def _find_scene(db: Session, series: Series, spec: dict[str, Any]) -> Scene | None:
    reuse_id = spec.get("reuse_scene_id")
    if reuse_id:
        return _linked_scene_or_error(series, str(reuse_id))
    return _find_linked_by_name_or_key(series.scenes or [], spec, "Scene")


def _find_linked_by_name_or_key(items: list[Any], spec: dict[str, Any], label: str) -> Any | None:
    stable_key = _stable_key(spec)
    by_key = [item for item in items if (item.meta_json or {}).get("asset_stable_key") == stable_key]
    if len(by_key) > 1:
        raise AssetDirectorError("AMBIGUOUS_ASSET_MATCH", f"{label} stable key matches multiple assets.", {"stable_key": stable_key})
    if by_key:
        return by_key[0]
    name = _norm(spec.get("name"))
    if not name:
        raise AssetDirectorError("ASSET_NAME_MISSING", f"{label} name is required.", {"stable_key": stable_key})
    by_name = [item for item in items if _norm(item.name) == name]
    if len(by_name) > 1:
        raise AssetDirectorError("AMBIGUOUS_ASSET_MATCH", f"{label} name matches multiple assets.", {"name": spec.get("name")})
    return by_name[0] if by_name else None


def _linked_character_or_error(series: Series, character_id: str) -> Character:
    for character in series.characters or []:
        if character.id == character_id:
            return character
    raise AssetDirectorError("ASSET_REUSE_NOT_LINKED", "Character reuse id is not linked to the series.", {"character_id": character_id})


def _linked_scene_or_error(series: Series, scene_id: str) -> Scene:
    for scene in series.scenes or []:
        if scene.id == scene_id:
            return scene
    raise AssetDirectorError("ASSET_REUSE_NOT_LINKED", "Scene reuse id is not linked to the series.", {"scene_id": scene_id})


def _bind_frames(storyboard: dict[str, Any], bindings: list[dict[str, Any]], characters: dict[str, Character], scenes: dict[str, Scene]) -> dict[str, Any]:
    by_frame_id = {str(row.get("frame_id")): row for row in bindings if isinstance(row, dict) and row.get("frame_id")}
    frames = storyboard.get("frames") if isinstance(storyboard.get("frames"), list) else []
    enriched = []
    for frame in frames:
        if not isinstance(frame, dict):
            enriched.append(frame)
            continue
        row = by_frame_id.get(str(frame.get("frame_id")))
        if not row:
            enriched.append(frame)
            continue
        item = dict(frame)
        scene_key = str(row.get("scene_stable_key") or "")
        if scene_key:
            item["scene_id"] = scenes[scene_key].id
        keys = [str(value) for value in row.get("character_stable_keys") or [] if value]
        if keys:
            item["character_ids"] = [characters[key].id for key in keys]
        enriched.append(item)
    return {**storyboard, "frames": enriched}


def _write_script_scope(episode: Episode, episode_row: dict[str, Any], characters: dict[str, Character], scenes: dict[str, Scene]) -> None:
    script = dict(episode.script_json or {})
    character_ids = [characters[_stable_key(spec)].id for spec in episode_row.get("characters") or []]
    scene_ids = [scenes[_stable_key(spec)].id for spec in episode_row.get("scenes") or []]
    if character_ids or scene_ids:
        script["episode_asset_scope"] = {
            "source": ASSET_DIRECTOR_SOURCE,
            "character_ids": list(dict.fromkeys(character_ids)),
            "scene_ids": list(dict.fromkeys(scene_ids)),
        }
        episode.script_json = script
        flag_modified(episode, "script_json")


def _asset_meta(series: Series, episode: Episode | None, spec: dict[str, Any]) -> dict[str, Any]:
    scope = str(spec.get("asset_scope") or "episode_only")
    if scope not in ASSET_SCOPES:
        raise AssetDirectorError("ASSET_SCOPE_INVALID", "Asset scope is invalid.", {"asset_scope": scope})
    return {
        "series_id": series.id,
        "episode_id": episode.id if episode else None,
        "asset_scope": scope,
        "asset_source": ASSET_DIRECTOR_SOURCE,
        "asset_stable_key": _stable_key(spec),
    }


def _merge_asset_meta(asset: Any, series: Series, episode: Episode | None, spec: dict[str, Any]) -> None:
    meta = dict(asset.meta_json or {})
    meta.update(_asset_meta(series, episode, spec))
    asset.meta_json = meta
    flag_modified(asset, "meta_json")


def _stable_key(spec: dict[str, Any]) -> str:
    key = str(spec.get("stable_key") or "").strip()
    if key:
        return key
    return _norm(spec.get("name"))


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _append_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _director_system_prompt() -> str:
    return "你是短剧全量资产导演。只输出 JSON，不要 Markdown。"


def _director_user_prompt(series: Series, episode: Episode) -> str:
    payload = {
        "series": {"id": series.id, "title": series.title, "logline": series.logline},
        "episode": {
            "id": episode.id,
            "episode_number": int(episode.episode_number),
            "title": episode.title,
            "script_json": episode.script_json if isinstance(episode.script_json, dict) else {},
            "storyboard_json": episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {},
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise AssetDirectorError("PLAN_INVALID_JSON", "Asset director output is not valid JSON.", {"raw": raw[:500]}) from exc
    if not isinstance(parsed, dict):
        raise AssetDirectorError("PLAN_INVALID_JSON", "Asset director output must be a JSON object.", {})
    return parsed
```

- [ ] **Step 2: Run contract tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py -q
```

Expected: PASS, 3 tests.

- [ ] **Step 3: Commit service**

```powershell
git add server/app/domains/ai_video_series/asset_director_service.py
git commit -m "feat: add full asset director service"
```

---

### Task 3: Production Start Integration

**Files:**
- Modify: `server/app/domains/video_production/production_run_service.py`
- Test: `server/tests/test_video_production_start_flow_contract.py`

- [ ] **Step 1: Add failing production-start test**

Append to `server/tests/test_video_production_start_flow_contract.py`:

```python
@pytest.mark.asyncio
async def test_start_flow_runs_asset_director_when_preparing_text_artifacts(db, monkeypatch):
    from app.domains.video_production.production_run_service import start_episode_production

    calls = []

    async def fake_director(db_session, series_id, episode_id):
        calls.append((series_id, episode_id))
        return {"ok": True, "artifact_id": "asset-plan-1"}

    monkeypatch.setattr(
        "app.domains.video_production.production_run_service.ensure_asset_director_plan_for_episode",
        fake_director,
    )

    series = Series(
        title="Asset Director Series",
        logline="A doctor solves crimes.",
        total_episodes=1,
        target_duration=10,
        status="draft",
        story_bible_json={"style_lock": {"locked": True, "characters": [], "scenes": []}},
    )
    db.add(series)
    db.flush()
    character = Character(name="Dr Lin", role_type="protagonist", gender="female")
    scene = Scene(name="Clinic", scene_type="indoor")
    db.add_all([character, scene])
    series.characters.append(character)
    series.scenes.append(scene)
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        script_json={"episode_asset_scope": {"source": "asset_director", "character_ids": [character.id], "scene_ids": [scene.id]}},
        storyboard_json={"frames": [{"frame_id": "frame-001", "scene_id": scene.id, "character_ids": [character.id], "duration": 5}]},
    )
    db.add(episode)
    db.commit()

    run = await start_episode_production(
        db,
        series_id=series.id,
        episode_id=episode.id,
        target_duration_seconds=10,
        prepare_text_artifacts=True,
    )

    assert run.series_id == series.id
    assert calls == [(series.id, episode.id)]
```
- [ ] **Step 2: Run the new test and verify failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py -k asset_director -q
```

Expected: FAIL because `ensure_asset_director_plan_for_episode` is not imported in `production_run_service.py`.

- [ ] **Step 3: Wire asset director into production start**

Modify imports near the existing `generate_series_story_plan` import in `server/app/domains/video_production/production_run_service.py`:

```python
from app.domains.ai_video_series.asset_director_service import ensure_asset_director_plan_for_episode
```

Inside `start_episode_production`, after script/storyboard draft generation and before final `episode_asset_scope` selection, add:

```python
    if prepare_text_artifacts:
        await ensure_asset_director_plan_for_episode(db, series_id, episode_id)
        db.refresh(series)
        db.refresh(episode)
        storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else storyboard
```

Place it before:

```python
    if episode_asset_scope_override is not None:
```

- [ ] **Step 4: Run production integration test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py -k asset_director -q
```

Expected: PASS.

- [ ] **Step 5: Run focused production contract tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit production integration**

```powershell
git add server/app/domains/video_production/production_run_service.py server/tests/test_video_production_start_flow_contract.py
git commit -m "feat: require asset director for prepared production"
```

---

### Task 4: Read Model Classification Fields

**Files:**
- Modify: `server/app/domains/ai_video_series/read_models.py`
- Test: `server/tests/test_asset_director_service.py`

- [ ] **Step 1: Add failing read-model assertion**

Append to `server/tests/test_asset_director_service.py`:

```python
def test_episode_asset_scope_payload_includes_asset_classification(db):
    from app.domains.ai_video_series.asset_director_service import apply_asset_director_plan
    from app.domains.ai_video_series.read_models import episode_asset_scope_payload

    series, ep1, _ep2 = _series_with_episode(db)
    plan = {
        "series_id": series.id,
        "recurring_characters": [],
        "episode_assets": [{
            "episode_number": 1,
            "characters": [{"stable_key": "guest", "name": "Guest Xu", "asset_scope": "guest"}],
            "scenes": [{"stable_key": "alley", "name": "Back Alley", "asset_scope": "episode_only", "scene_type": "outdoor"}],
            "frame_bindings": [],
        }],
    }
    apply_asset_director_plan(db, series.id, plan)

    payload = episode_asset_scope_payload(db, ep1)

    assert payload["characters"][0]["asset_scope"] == "guest"
    assert payload["characters"][0]["asset_source"] == "asset_director"
    assert payload["scenes"][0]["asset_scope"] == "episode_only"
    assert payload["scenes"][0]["series_id"] == series.id
    assert payload["scenes"][0]["episode_id"] == ep1.id
```

- [ ] **Step 2: Run read-model test and verify failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py -k classification -q
```

Expected: FAIL because classification fields are missing.

- [ ] **Step 3: Add metadata fields to asset usage payloads**

Modify `episode_asset_usage_items` in `server/app/domains/ai_video_series/read_models.py` so each result item includes metadata:

```python
        meta = getattr(row, "meta_json", None) or {}
        item.setdefault("asset_scope", meta.get("asset_scope", "series_recurring"))
        item.setdefault("asset_source", meta.get("asset_source", "manual"))
        item.setdefault("series_id", meta.get("series_id"))
        item.setdefault("episode_id", meta.get("episode_id"))
```

The snippet belongs inside the loop that builds `result`, after `item.setdefault("name", ...)`.

- [ ] **Step 4: Run read-model and service tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit read model**

```powershell
git add server/app/domains/ai_video_series/read_models.py server/tests/test_asset_director_service.py
git commit -m "feat: expose asset classification in episode scope"
```

---

### Task 5: Artifact Consumption Binding

**Files:**
- Modify: `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`
- Test: `server/tests/test_asset_director_service.py`

- [ ] **Step 1: Add failing artifact binding test**

Append to `server/tests/test_asset_director_service.py`:

```python
def test_asset_director_plan_is_bound_to_video_run_consumers(db):
    from app.domains.ai_video_series.asset_director_service import apply_asset_director_plan
    from app.domains.ai_text_artifacts.ai_text_artifact_service import AITextArtifactService
    from app.db.models import VideoProductionRun

    series, ep1, _ep2 = _series_with_episode(db)
    apply_asset_director_plan(db, series.id, {"series_id": series.id, "recurring_characters": [], "episode_assets": []})
    run = VideoProductionRun(series_id=series.id, episode_id=ep1.id, status="created", current_stage="created")
    db.add(run)
    db.commit()

    bindings = AITextArtifactService(db).bind_latest_approved_for_episode_run(
        series_id=series.id,
        episode_id=ep1.id,
        run_id=run.id,
    )

    assert any(binding.metadata_json["artifact_type"] == "asset_director_plan" for binding in bindings)
```

- [ ] **Step 2: Run binding test and verify failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py -k bound -q
```

Expected: FAIL because `asset_director_plan` is not in `SERIES_RUN_ARTIFACT_TYPES`.

- [ ] **Step 3: Include asset director artifact in series run artifacts**

Modify `SERIES_RUN_ARTIFACT_TYPES` in `server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`:

```python
SERIES_RUN_ARTIFACT_TYPES = (
    "series_bible",
    "series_story_plan",
    "season_arc",
    "continuity_ledger",
    "asset_director_plan",
)
```

- [ ] **Step 4: Run binding test**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py -k bound -q
```

Expected: PASS.

- [ ] **Step 5: Commit binding**

```powershell
git add server/app/domains/ai_text_artifacts/ai_text_artifact_service.py server/tests/test_asset_director_service.py
git commit -m "feat: bind asset director artifacts to production runs"
```

---

### Task 6: Series Detail Classification Badges

**Files:**
- Modify: `web/src/views/SeriesDetailPage.vue`
- Test: `web/src/__tests__/series-detail-agency.test.js`

- [ ] **Step 1: Add failing frontend assertion**

In `web/src/__tests__/series-detail-agency.test.js`, add an episode asset payload that includes classification fields in an existing series detail render test, then assert:

```javascript
expect(wrapper.text()).toContain('客串')
expect(wrapper.text()).toContain('单集')
```

Use this payload shape in the mocked episode:

```javascript
asset_scope: {
  character_ids: ['char-guest'],
  scene_ids: ['scene-alley'],
  characters: [{ id: 'char-guest', name: 'Guest Xu', asset_scope: 'guest', asset_source: 'asset_director' }],
  scenes: [{ id: 'scene-alley', name: 'Back Alley', asset_scope: 'episode_only', asset_source: 'asset_director' }],
}
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
npm exec vitest run src/__tests__/series-detail-agency.test.js
```

Expected: FAIL because no classification label is rendered.

- [ ] **Step 3: Add label helpers**

In `web/src/views/SeriesDetailPage.vue`, add:

```javascript
function assetScopeLabel(scope) {
  return {
    series_recurring: '常驻',
    episode_only: '单集',
    guest: '客串',
    location_recurring: '常驻地点',
  }[scope] || ''
}
```

- [ ] **Step 4: Render badges beside episode assets**

In the character and scene chips in the expanded episode asset sections, add:

```vue
<span v-if="assetScopeLabel(character.asset_scope)" class="ml-1 text-cyan-300">{{ assetScopeLabel(character.asset_scope) }}</span>
```

and:

```vue
<span v-if="assetScopeLabel(scene.asset_scope)" class="ml-1 text-cyan-300">{{ assetScopeLabel(scene.asset_scope) }}</span>
```

- [ ] **Step 5: Run frontend test**

Run:

```powershell
npm exec vitest run src/__tests__/series-detail-agency.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit UI**

```powershell
git add web/src/views/SeriesDetailPage.vue web/src/__tests__/series-detail-agency.test.js
git commit -m "feat: show episode asset classifications"
```

---

### Task 7: Final Verification

**Files:**
- No file edits.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_asset_director_service.py server/tests/test_video_production_start_flow_contract.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused tests**

Run:

```powershell
npm exec vitest run src/__tests__/series-detail-agency.test.js src/__tests__/ai-text-artifact-workbench.test.js
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
npm run build
```

Expected: PASS. Existing large chunk warnings may appear.

- [ ] **Step 4: Check worktree**

Run:

```powershell
git status --short
```

Expected: no output.

---

## Self-Review

Spec coverage:

- Full asset director stage: Task 2.
- Per-episode asset creation: Task 1 and Task 2.
- Recurring asset reuse: Task 1 and Task 2.
- Asset classification metadata: Task 2 and Task 4.
- Storyboard frame binding: Task 1 and Task 2.
- Production gate: Task 3.
- Artifact traceability: Task 5.
- UI visibility: Task 6.
- Verification: Task 7.

Placeholder scan:

- The plan contains no red-flag markers or open-ended implementation slots.

Type consistency:

- `asset_director_plan`, `asset_scope`, `asset_source`, `series_id`, `episode_id`, `character_ids`, and `scene_id` use the same names in backend service, read model, artifact binding, and UI.
