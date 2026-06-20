# Episode Asset Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every series episode gets a strict, non-empty character and scene usage set generated from the episode story needs, then script generation, storyboard frames, production planning, API responses, and the series detail UI all consume that episode-specific scope.

**Architecture:** Add a focused episode asset scope normalizer service that validates existing asset IDs, creates story-required assets from generator output, links new assets to the series asset pool, and writes normalized `asset_usage` back into approved story artifacts. Keep the first implementation artifact-backed: `episode_outline`, `episode.script_json.episode_asset_scope`, and `episode.storyboard_json.frames[]`. Do not add `episode_characters` or `episode_scenes` tables in this pass.

**Tech Stack:** FastAPI, SQLAlchemy ORM, existing `AITextArtifactService`, existing script pipeline Pydantic models, Pytest, Vue 3, Vitest.

---

## Task 1: Add Episode Asset Scope Normalizer

**Files:**

- Create `server/app/services/episode_asset_scope_service.py`
- Create `server/tests/test_episode_asset_scope_service.py`

**Success criteria:**

- Valid episode outline IDs are de-duplicated, validated, and summarized under `asset_usage`.
- Generated character and scene specs create real `Character` and `Scene` rows and link them to `series.characters` / `series.scenes`.
- Empty series asset pools get deterministic fallback character and scene assets.
- IDs that exist but are not linked to the current series raise a stable validation error.

**Steps:**

- [ ] Write failing tests in `server/tests/test_episode_asset_scope_service.py`.

```python
import pytest

from app.db_models import Character, Episode, Scene, Series
from app.services.episode_asset_scope_service import (
    EpisodeAssetScopeError,
    normalize_episode_asset_scope,
)


def test_normalizes_existing_episode_asset_ids(db):
    series = Series(title="Family Ledger", total_episodes=1, status="draft")
    char = Character(name="Lin Xia", role_type="protagonist")
    scene = Scene(name="Old Pharmacy", scene_type="indoor")
    series.characters.append(char)
    series.scenes.append(scene)
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(
        db,
        series,
        episode,
        {
            "episode_number": 1,
            "title": "Receipt",
            "character_ids": [char.id, char.id],
            "scene_ids": [scene.id],
        },
    )

    assert outline["character_ids"] == [char.id]
    assert outline["scene_ids"] == [scene.id]
    assert outline["asset_usage"]["characters"][0]["source"] == "existing"
    assert outline["asset_usage"]["characters"][0]["name"] == "Lin Xia"
    assert outline["asset_usage"]["scenes"][0]["name"] == "Old Pharmacy"


def test_creates_generated_assets_and_links_to_series(db):
    series = Series(title="Family Ledger", total_episodes=1, status="draft")
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(
        db,
        series,
        episode,
        {
            "episode_number": 1,
            "title": "Witness",
            "generated_assets": {
                "characters": [
                    {
                        "name": "Aunt Qiu",
                        "role_type": "supporting",
                        "gender": "female",
                        "age_range": "50-60",
                        "personality": "Keeps family secrets but cracks under pressure.",
                        "appearance_desc": "Short silver hair, tired eyes, careful posture.",
                        "outfit_desc": "Dark wool cardigan and jade bracelet.",
                        "usage": "Reveals the missing ledger.",
                    }
                ],
                "scenes": [
                    {
                        "name": "Rainy Bus Stop",
                        "scene_type": "outdoor",
                        "location_desc": "A narrow roadside stop under flickering lights.",
                        "lighting": "night",
                        "mood": "tense",
                        "usage": "Secret handoff location.",
                    }
                ],
            },
        },
    )
    db.refresh(series)

    assert len(outline["character_ids"]) == 1
    assert len(outline["scene_ids"]) == 1
    assert series.characters[0].name == "Aunt Qiu"
    assert series.scenes[0].name == "Rainy Bus Stop"
    assert series.characters[0].meta_json["source"] == "episode_story_planning"
    assert series.characters[0].meta_json["generated_for_episode_id"] == episode.id
    assert outline["asset_usage"]["characters"][0]["source"] == "generated"


def test_fallback_creates_minimal_assets_when_pool_is_empty(db):
    series = Series(title="Zero Pool", total_episodes=1, status="draft")
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, episode])
    db.commit()

    outline = normalize_episode_asset_scope(db, series, episode, {"episode_number": 1})
    db.refresh(series)

    assert outline["character_ids"] == [series.characters[0].id]
    assert outline["scene_ids"] == [series.scenes[0].id]
    assert outline["asset_usage"]["characters"][0]["source"] == "fallback"
    assert outline["asset_usage"]["scenes"][0]["source"] == "fallback"


def test_rejects_asset_ids_not_linked_to_series(db):
    series = Series(title="Owned", total_episodes=1, status="draft")
    other = Character(name="Other Series Lead", role_type="protagonist")
    episode = Episode(series=series, episode_number=1)
    db.add_all([series, other, episode])
    db.commit()

    with pytest.raises(EpisodeAssetScopeError) as exc:
        normalize_episode_asset_scope(
            db,
            series,
            episode,
            {"episode_number": 1, "character_ids": [other.id], "scene_ids": []},
        )

    assert exc.value.code == "EPISODE_ASSET_INVALID"
```

- [ ] Run the focused test and confirm it fails for the missing service.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_episode_asset_scope_service.py -q
```

- [ ] Implement `server/app/services/episode_asset_scope_service.py` with these public contracts.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import Character, Episode, Scene, Series


@dataclass
class EpisodeAssetScopeError(ValueError):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def normalize_episode_asset_scope(
    db: Session,
    series: Series,
    episode: Episode,
    outline: dict[str, Any],
    *,
    fallback_source: str = "episode_outline",
) -> dict[str, Any]:
    """Return a copy of the outline with validated episode character and scene IDs."""
    normalized = dict(outline or {})
    generated_assets = normalized.get("generated_assets") if isinstance(normalized.get("generated_assets"), dict) else {}
    source_by_character_id: dict[str, str] = {}
    source_by_scene_id: dict[str, str] = {}

    _create_generated_characters(db, series, episode, generated_assets.get("characters") or [], source_by_character_id)
    _create_generated_scenes(db, series, episode, generated_assets.get("scenes") or [], source_by_scene_id)
    db.flush()

    character_ids = _dedupe_strings(normalized.get("character_ids"))
    scene_ids = _dedupe_strings(normalized.get("scene_ids"))

    if not character_ids:
        character_ids = list(source_by_character_id)
    if not scene_ids:
        scene_ids = list(source_by_scene_id)

    if not character_ids:
        fallback_character = _fallback_character(db, series, episode)
        character_ids = [fallback_character.id]
        source_by_character_id[fallback_character.id] = "fallback"
    if not scene_ids:
        fallback_scene = _fallback_scene(db, series, episode)
        scene_ids = [fallback_scene.id]
        source_by_scene_id[fallback_scene.id] = "fallback"

    characters = _validate_characters(db, series, character_ids)
    scenes = _validate_scenes(db, series, scene_ids)

    normalized["character_ids"] = [character.id for character in characters]
    normalized["scene_ids"] = [scene.id for scene in scenes]
    normalized["asset_usage"] = {
        "characters": [
            _character_usage(character, source_by_character_id.get(character.id, "existing"), fallback_source)
            for character in characters
        ],
        "scenes": [
            _scene_usage(scene, source_by_scene_id.get(scene.id, "existing"), fallback_source)
            for scene in scenes
        ],
    }
    normalized["generated_assets"] = {
        "characters": list(generated_assets.get("characters") or []),
        "scenes": list(generated_assets.get("scenes") or []),
    }
    return normalized
```

Implementation details:

- `_dedupe_strings(value)` keeps insertion order and drops blank values.
- `_validate_characters` and `_validate_scenes` query by ID, then verify every resolved row is already in the current series relation.
- `_create_generated_characters` and `_create_generated_scenes` dedupe by case-insensitive name inside the current series before creating new rows.
- Fallback rows use `meta_json.source = "episode_story_planning"` and `meta_json.generated_for_episode_id = episode.id`; their `asset_usage.source` is `"fallback"`.
- Invalid IDs raise `EpisodeAssetScopeError(code="EPISODE_ASSET_INVALID", message="Episode asset IDs must exist and be linked to the series.", details={...})`.

- [ ] Re-run the focused test until it passes.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_episode_asset_scope_service.py -q
```

- [ ] Commit only the new service and tests.

```powershell
git add server/app/services/episode_asset_scope_service.py server/tests/test_episode_asset_scope_service.py
git commit -m "feat: normalize episode asset scope"
```

## Task 2: Wire Normalizer Into Story Planning

**Files:**

- Modify `server/app/services/series_planning_service.py`
- Modify `server/app/services/story_generator_expert.py`
- Modify `server/tests/test_series_planning_service.py`

**Success criteria:**

- Story planning stores per-episode `character_ids`, `scene_ids`, and `asset_usage` instead of copying the full series pool into every outline.
- The story generator prompt and response schema explicitly allow `generated_assets` and `asset_usage`.
- Human-approved `episode_outline` artifacts keep valid explicit IDs.
- Story planning creates and links new story-required assets returned by the story generator.

**Steps:**

- [ ] Update `server/tests/test_series_planning_service.py` with failing coverage.

Key assertions:

```python
def test_generate_series_story_plan_creates_episode_specific_assets_from_story_output(db, monkeypatch):
    series, ep1, ep2, lead, home = _series_with_two_episodes_and_assets(db)
    payload = _planning_payload(total_episodes=2)
    payload["episode_outlines"][0]["character_ids"] = [lead.id]
    payload["episode_outlines"][0]["scene_ids"] = [home.id]
    payload["episode_outlines"][1]["character_ids"] = []
    payload["episode_outlines"][1]["scene_ids"] = []
    payload["episode_outlines"][1]["generated_assets"] = {
        "characters": [{"name": "Doctor Ren", "role_type": "supporting", "usage": "Names the real heir."}],
        "scenes": [{"name": "Clinic Archive", "scene_type": "indoor", "usage": "Hides the adoption file."}],
    }
    monkeypatch.setattr(
        "app.services.series_planning_service.generate_story_plan_with_expert",
        AsyncMock(return_value=StoryGeneratorResult(parsed=payload, source_type="ai", model_trace={})),
    )

    result = anyio.run(generate_series_story_plan, db, series.id, force=True)
    ep1_outline = _latest_outline(db, ep1.id)
    ep2_outline = _latest_outline(db, ep2.id)
    db.refresh(series)

    assert ep1_outline["character_ids"] == [lead.id]
    assert ep1_outline["scene_ids"] == [home.id]
    assert ep2_outline["character_ids"] != ep1_outline["character_ids"]
    assert ep2_outline["scene_ids"] != ep1_outline["scene_ids"]
    assert any(character.name == "Doctor Ren" for character in series.characters)
    assert any(scene.name == "Clinic Archive" for scene in series.scenes)
    assert ep2_outline["asset_usage"]["characters"][0]["source"] == "generated"
    assert result["status"] in {"completed", "fallback"}
```

Also add:

- `test_generate_series_story_plan_fallback_creates_minimal_episode_assets`
- `test_human_approved_episode_outline_preserves_valid_asset_ids`
- `test_story_generator_prompt_requests_generated_assets_and_asset_usage`

- [ ] Run the story planning tests and confirm they fail for missing normalization.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py -q
```

- [ ] Update `server/app/services/story_generator_expert.py`.

Prompt/schema requirements:

```python
STORY_PLAN_OUTPUT_SCHEMA["properties"]["episode_outlines"]["items"] = {
    "type": "object",
    "additionalProperties": True,
    "required": ["episode_number", "title", "character_ids", "scene_ids"],
    "properties": {
        "episode_number": {"type": "integer"},
        "title": {"type": "string"},
        "character_ids": {"type": "array", "items": {"type": "string"}},
        "scene_ids": {"type": "array", "items": {"type": "string"}},
        "asset_usage": {"type": "object"},
        "generated_assets": {"type": "object"},
    },
}
```

Add prompt text in `_build_prompts`:

```python
"每集必须选择本集实际出现的 character_ids 和 scene_ids；不要把全系列资产池机械复制到每一集。",
"如果本集需要新角色或新场景，请在 generated_assets.characters / generated_assets.scenes 中给出可创建资产的字段。",
"asset_usage 用一句话说明每个角色或场景在本集中的剧情作用。",
```

Add existing asset summaries to the model context so the story generator can reason by name, not just ID:

```python
"series_asset_pool": {
    "characters": [
        {"id": character.id, "name": character.name, "role_type": character.role_type}
        for character in series.characters
    ],
    "scenes": [
        {"id": scene.id, "name": scene.name, "scene_type": scene.scene_type}
        for scene in series.scenes
    ],
},
```

- [ ] Update `server/app/services/series_planning_service.py`.

Use the normalizer after the existing outline parsing:

```python
from app.services.episode_asset_scope_service import normalize_episode_asset_scope


def _normalize_and_scope_episode_outline(
    db: Session,
    *,
    series: Series,
    episode: Episode,
    raw_outline: dict[str, Any],
    total_episodes: int,
    fallback_character_ids: list[str],
    fallback_scene_ids: list[str],
    source_type: str,
) -> dict[str, Any]:
    outline = _normalize_episode_outline(
        raw_outline,
        episode.episode_number,
        total_episodes,
        fallback_character_ids,
        fallback_scene_ids,
    )
    return normalize_episode_asset_scope(
        db,
        series,
        episode,
        outline,
        fallback_source=source_type or "episode_outline",
    )
```

Apply that helper in both `generate_series_story_plan` and `ensure_series_continuity_artifacts` before creating or approving `episode_outline` artifacts.

- [ ] Preserve valid human-approved outlines:

```python
existing = service.latest_approved(
    target_type="episode",
    target_id=episode.id,
    artifact_type="episode_outline",
)
if existing and not force:
    normalized = normalize_episode_asset_scope(
        db,
        series,
        episode,
        existing.content_json if isinstance(existing.content_json, dict) else {},
        fallback_source=existing.source_type or "episode_outline",
    )
    if normalized != existing.content_json:
        existing.content_json = normalized
        existing.content_text = json.dumps(normalized, ensure_ascii=False)
        flag_modified(existing, "content_json")
    continue
```

- [ ] Re-run story planning tests until they pass.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_series_planning_service.py server/tests/test_episode_asset_scope_service.py -q
```

- [ ] Commit only the story planning integration.

```powershell
git add server/app/services/series_planning_service.py server/app/services/story_generator_expert.py server/tests/test_series_planning_service.py
git commit -m "feat: generate episode asset scopes during story planning"
```

## Task 3: Make Script Generation Consume Episode Asset Scope

**Files:**

- Modify `server/app/models/script.py`
- Modify `server/app/services/production_run_service.py`
- Modify `server/app/services/script_pipeline.py`
- Modify `server/tests/test_video_production_start_flow_contract.py`
- Modify `server/tests/test_script_pipeline.py`

**Success criteria:**

- Script generation prompt has a primary "本集资产清单" section sourced from the current episode outline.
- The broader series asset pool remains secondary continuity context.
- `episode.script_json.episode_asset_scope` is persisted with non-empty IDs and source metadata.

**Steps:**

- [ ] Add failing prompt and snapshot tests.

Prompt test shape in `server/tests/test_video_production_start_flow_contract.py`:

```python
async def test_episode_script_prompt_uses_episode_asset_scope_as_primary_context(db, monkeypatch):
    series, episode, current_character, current_scene, unrelated_character = _series_with_asset_scope(db)
    _approve_episode_outline(
        db,
        series,
        episode,
        {
            "episode_number": 1,
            "character_ids": [current_character.id],
            "scene_ids": [current_scene.id],
            "asset_usage": {
                "characters": [{"id": current_character.id, "name": current_character.name, "usage": "Confronts the lie."}],
                "scenes": [{"id": current_scene.id, "name": current_scene.name, "usage": "Family confrontation."}],
            },
        },
    )
    captured = {}

    async def fake_start(self, db_arg, **kwargs):
        captured.update(kwargs)
        raise RuntimeError("stop after prompt capture")

    monkeypatch.setattr("app.services.production_run_service.PipelineManager.start_or_resume", fake_start)

    with pytest.raises(RuntimeError):
        await generate_episode_script_storyboard(db, series_id=series.id, episode_id=episode.id)

    prompt = captured["source_prompt"]
    assert "本集资产清单" in prompt
    assert current_character.name in prompt
    assert current_scene.name in prompt
    assert prompt.index("本集资产清单") < prompt.index("系列资产池")
    assert captured["episode_asset_scope"]["character_ids"] == [current_character.id]
    assert captured["episode_asset_scope"]["scene_ids"] == [current_scene.id]
```

Snapshot test shape in `server/tests/test_script_pipeline.py`:

```python
def test_script_snapshot_persists_episode_asset_scope():
    script = _valid_episode_script(
        episode_asset_scope={
            "character_ids": ["char-1"],
            "scene_ids": ["scene-1"],
            "source": "episode_outline",
        }
    )

    snapshot = PipelineManager()._script_snapshot(script, "script-1")

    assert snapshot["episode_asset_scope"] == {
        "character_ids": ["char-1"],
        "scene_ids": ["scene-1"],
        "source": "episode_outline",
    }
```

- [ ] Run focused tests and confirm they fail.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py server/tests/test_script_pipeline.py -q
```

- [ ] Update `server/app/models/script.py`.

```python
class EpisodeScript(BaseModel):
    series_id: str
    episode_id: str
    source_prompt: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    target_duration_seconds: int = Field(..., ge=1)
    episode_asset_scope: dict[str, Any] = Field(default_factory=dict)
    dramatic_beats: DramaticBeatList
    scene_outlines: SceneOutlineList
    visual_shots: VisualShotList
    agency_trace: dict[str, Any] = Field(default_factory=dict)
```

- [ ] Update `server/app/services/production_run_service.py`.

Add helpers:

```python
def _asset_name_maps(series: Series) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {character.id: character.name for character in series.characters or []},
        {scene.id: scene.name for scene in series.scenes or []},
    )


def _episode_asset_scope_from_outline(service: AITextArtifactService, series: Series, episode: Episode) -> dict:
    artifact = service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
    )
    content = artifact.content_json if artifact and isinstance(artifact.content_json, dict) else {}
    character_ids = [value for value in content.get("character_ids") or [] if isinstance(value, str) and value]
    scene_ids = [value for value in content.get("scene_ids") or [] if isinstance(value, str) and value]
    character_names, scene_names = _asset_name_maps(series)
    return {
        "character_ids": list(dict.fromkeys(character_ids)),
        "scene_ids": list(dict.fromkeys(scene_ids)),
        "source": "episode_outline" if artifact else "missing_episode_outline",
        "asset_usage": content.get("asset_usage") if isinstance(content.get("asset_usage"), dict) else {},
        "characters": [{"id": asset_id, "name": character_names.get(asset_id, asset_id)} for asset_id in character_ids],
        "scenes": [{"id": asset_id, "name": scene_names.get(asset_id, asset_id)} for asset_id in scene_ids],
    }
```

In `_script_generation_source_prompt`, add the primary section before approved story context:

```python
episode_scope = _episode_asset_scope_from_outline(service, series, episode)
if episode_scope["character_ids"] or episode_scope["scene_ids"]:
    parts.extend([
        "本集资产清单：",
        json.dumps(episode_scope, ensure_ascii=False),
        "系列资产池仅用于连续性参考，不得替代本集资产清单：",
        json.dumps(_series_asset_pool_summary(series), ensure_ascii=False),
    ])
```

Pass the same scope into `PipelineManager.start_or_resume` in both `_try_generate_script_storyboard` and `generate_episode_script_storyboard`.

- [ ] Update `server/app/services/script_pipeline.py`.

Add the optional parameter:

```python
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
    episode_asset_scope: dict[str, Any] | None = None,
) -> EpisodeScript:
```

Use it when constructing `EpisodeScript`:

```python
result = EpisodeScript(
    series_id=series_id,
    episode_id=episode_id,
    source_prompt=source_prompt,
    tags=tags,
    target_duration_seconds=target_duration_seconds,
    episode_asset_scope=episode_asset_scope or {},
    dramatic_beats=beats,
    scene_outlines=scenes,
    visual_shots=shots,
    agency_trace=self._agency_trace(run),
)
```

Persist it:

```python
def _script_snapshot(self, script: EpisodeScript, db_script_id: str) -> dict[str, Any]:
    return {
        "source": "dramatic_script_pipeline",
        "script_id": db_script_id,
        "source_prompt": script.source_prompt,
        "tags": script.tags,
        "target_duration_seconds": script.target_duration_seconds,
        "episode_asset_scope": dict(script.episode_asset_scope or {}),
        "dramatic_beats": script.dramatic_beats.model_dump(mode="json"),
        "scene_outlines": script.scene_outlines.model_dump(mode="json"),
        "visual_shots": script.visual_shots.model_dump(mode="json"),
        "agency_trace": script.agency_trace,
    }
```

- [ ] Re-run focused tests until they pass.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py server/tests/test_script_pipeline.py -q
```

- [ ] Commit only the script scope integration.

```powershell
git add server/app/models/script.py server/app/services/production_run_service.py server/app/services/script_pipeline.py server/tests/test_video_production_start_flow_contract.py server/tests/test_script_pipeline.py
git commit -m "feat: pass episode assets into script generation"
```

## Task 4: Persist Frame-Level Asset IDs in Storyboards

**Files:**

- Modify `server/app/services/script_pipeline.py`
- Modify `server/tests/test_script_pipeline.py`

**Success criteria:**

- Every storyboard frame produced by the script pipeline has a `scene_id`.
- Every storyboard frame has non-empty `character_ids`.
- Ambiguous missing scene inference raises `ScriptGenerationError` with `error_code="EPISODE_ASSET_SCOPE_MISSING"`.

**Steps:**

- [ ] Add failing tests.

```python
def test_storyboard_snapshot_copies_episode_asset_scope_to_frames():
    script = _valid_episode_script(
        episode_asset_scope={
            "character_ids": ["char-1"],
            "scene_ids": ["scene-1"],
            "source": "episode_outline",
        }
    )

    storyboard = PipelineManager()._storyboard_snapshot(script)

    assert storyboard["frames"][0]["scene_id"] == "scene-1"
    assert storyboard["frames"][0]["character_ids"] == ["char-1"]


def test_storyboard_snapshot_blocks_when_asset_scope_is_missing():
    script = _valid_episode_script(episode_asset_scope={"character_ids": [], "scene_ids": []})

    with pytest.raises(ScriptGenerationError) as exc:
        PipelineManager()._storyboard_snapshot(script)

    assert exc.value.error_code == "EPISODE_ASSET_SCOPE_MISSING"
```

- [ ] Run the script pipeline tests and confirm the new tests fail.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline.py -q
```

- [ ] Add a small resolver in `server/app/services/script_pipeline.py`.

```python
def _frame_asset_ids(script: EpisodeScript, shot: VisualShot) -> tuple[str, list[str]]:
    scope = script.episode_asset_scope if isinstance(script.episode_asset_scope, dict) else {}
    scene_ids = [value for value in scope.get("scene_ids") or [] if isinstance(value, str) and value]
    character_ids = [value for value in scope.get("character_ids") or [] if isinstance(value, str) and value]
    if not scene_ids or not character_ids:
        raise ScriptGenerationError(
            "Episode asset scope must include at least one scene and one character before storyboard export.",
            stage=PipelineStage.VISUAL_SHOTS.value,
            error_code="EPISODE_ASSET_SCOPE_MISSING",
        )
    scene_map = scope.get("scene_by_scene_number") if isinstance(scope.get("scene_by_scene_number"), dict) else {}
    mapped_scene_id = scene_map.get(str(shot.scene_number)) or scene_map.get(shot.scene_number)
    scene_id = str(mapped_scene_id or scene_ids[0])
    return scene_id, list(dict.fromkeys(character_ids))
```

Use it while creating each frame:

```python
for shot in script.visual_shots.shots:
    scene_id, character_ids = _frame_asset_ids(script, shot)
    frames.append({
        "frame_id": f"shot-{shot.shot_number:03d}",
        "scene_id": scene_id,
        "character_ids": character_ids,
        "image_prompt": shot.visual_prompt,
        "video_prompt": shot.video_prompt,
        "narration": shot.narration,
        "duration": shot.duration,
        "action": shot.beat_type.value,
        "emotion": shot.beat_type.value,
        "shot_type": "dramatic_script_pipeline",
    })
```

- [ ] Re-run script pipeline tests until they pass.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_script_pipeline.py -q
```

- [ ] Commit only the storyboard frame ID changes.

```powershell
git add server/app/services/script_pipeline.py server/tests/test_script_pipeline.py
git commit -m "feat: persist episode asset ids on storyboard frames"
```

## Task 5: Add Production Preflight for Episode Asset Scope

**Files:**

- Modify `server/app/services/production_errors.py`
- Modify `server/app/services/production_run_service.py`
- Modify `server/tests/test_video_production_start_flow_contract.py`

**Success criteria:**

- Production start refuses episodes that have no episode asset scope and no frame-level asset IDs.
- The refusal uses a stable repairable error code.
- Existing `ProductionScene.scene_id` and `ProductionShot.character_ids` continue to receive IDs from frames.

**Steps:**

- [ ] Add failing tests in `server/tests/test_video_production_start_flow_contract.py`.

```python
async def test_video_production_blocks_when_episode_asset_scope_is_missing(db):
    series, episode = _series_with_locked_style(db)
    episode.storyboard_json = {
        "frames": [{"frame_id": "shot-001", "duration": 2, "image_prompt": "Prompt", "video_prompt": "Move"}]
    }
    db.commit()

    with pytest.raises(ProductionRepairableError) as exc:
        await start_episode_production(
            db,
            series_id=series.id,
            episode_id=episode.id,
            prepare_text_artifacts=False,
        )

    assert exc.value.code == ProductionErrorCode.EPISODE_ASSET_SCOPE_MISSING


def test_video_production_keeps_frame_asset_ids(db):
    series, episode, character, scene = _series_with_locked_style_and_episode_assets(db)
    episode.storyboard_json = {
        "frames": [
            {
                "frame_id": "shot-001",
                "scene_id": scene.id,
                "character_ids": [character.id],
                "duration": 2,
                "image_prompt": "Prompt",
                "video_prompt": "Move",
            }
        ]
    }
    db.commit()

    plan = create_episode_production_plan(db, series.id, episode.id)

    production_scene = plan.episodes[0].scenes[0]
    assert production_scene.scene_id == scene.id
    assert production_scene.shots[0].character_ids == [character.id]
```

- [ ] Run the focused tests and confirm they fail.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py -q
```

- [ ] Add `EPISODE_ASSET_SCOPE_MISSING` to `ProductionErrorCode`.

```python
EPISODE_ASSET_SCOPE_MISSING = "EPISODE_ASSET_SCOPE_MISSING"
```

- [ ] Add a preflight helper in `server/app/services/production_run_service.py`.

```python
def _ensure_episode_asset_scope_ready(series: Series, episode: Episode) -> None:
    storyboard = episode.storyboard_json if isinstance(episode.storyboard_json, dict) else {}
    frames = storyboard.get("frames") if isinstance(storyboard.get("frames"), list) else []
    has_frame_scope = any(
        isinstance(frame, dict) and frame.get("scene_id") and frame.get("character_ids")
        for frame in frames
    )
    script = episode.script_json if isinstance(episode.script_json, dict) else {}
    script_scope = script.get("episode_asset_scope") if isinstance(script.get("episode_asset_scope"), dict) else {}
    has_script_scope = bool(script_scope.get("character_ids")) and bool(script_scope.get("scene_ids"))
    if has_frame_scope or has_script_scope:
        return
    raise ProductionRepairableError(
        code=ProductionErrorCode.EPISODE_ASSET_SCOPE_MISSING,
        message="本集缺少角色或场景作用域，无法进入视频生产。",
        repair_action="先生成或修复本集故事规划和剧本分镜，让每个分镜带有 scene_id 与 character_ids。",
        repair_route=f"/series/{series.id}",
        retryable=False,
        affected_ids=[episode.id],
    )
```

Call it before production plan creation or production run start, in the same service path that already validates approved text artifacts.

- [ ] Re-run production start flow tests until they pass.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_video_production_start_flow_contract.py -q
```

- [ ] Commit only production readiness changes.

```powershell
git add server/app/services/production_errors.py server/app/services/production_run_service.py server/tests/test_video_production_start_flow_contract.py
git commit -m "feat: block production without episode assets"
```

## Task 6: Expose Episode Asset Scope in API and UI

**Files:**

- Modify `server/app/routers/series.py`
- Modify `server/tests/test_series_api.py`
- Modify `web/src/views/SeriesDetailPage.vue`
- Modify existing or nearest Vue test for series detail rendering under `web/src/__tests__/`

**Success criteria:**

- Series detail response includes `episodes[].asset_scope`.
- The UI shows series asset pool separately from each episode's "本集角色" and "本集场景".
- Missing episode assets show a compact warning on the episode card.
- Generated episode assets are labeled as new when `asset_usage.source == "generated"`.

**Steps:**

- [ ] Add failing API test in `server/tests/test_series_api.py`.

```python
def test_get_series_detail_includes_episode_asset_scope(client, db):
    series, episode, character, scene = _series_with_episode_outline_asset_usage(db)

    resp = client.get(f"/api/series/{series.id}")

    assert resp.status_code == 200
    episode_payload = resp.json()["episodes"][0]
    assert episode_payload["asset_scope"]["character_ids"] == [character.id]
    assert episode_payload["asset_scope"]["scene_ids"] == [scene.id]
    assert episode_payload["asset_scope"]["characters"][0]["name"] == character.name
    assert episode_payload["asset_scope"]["scenes"][0]["name"] == scene.name
```

- [ ] Update `server/app/routers/series.py`.

Add helpers:

```python
def _episode_asset_scope_payload(db: Session, episode: Episode) -> dict:
    service = AITextArtifactService(db)
    artifact = service.latest_approved(
        target_type="episode",
        target_id=episode.id,
        artifact_type="episode_outline",
    )
    content = artifact.content_json if artifact and isinstance(artifact.content_json, dict) else {}
    script = episode.script_json if isinstance(episode.script_json, dict) else {}
    script_scope = script.get("episode_asset_scope") if isinstance(script.get("episode_asset_scope"), dict) else {}
    character_ids = list(dict.fromkeys(content.get("character_ids") or script_scope.get("character_ids") or []))
    scene_ids = list(dict.fromkeys(content.get("scene_ids") or script_scope.get("scene_ids") or []))
    usage = content.get("asset_usage") if isinstance(content.get("asset_usage"), dict) else {}
    return {
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "characters": usage.get("characters") or [],
        "scenes": usage.get("scenes") or [],
        "generated_assets": content.get("generated_assets") if isinstance(content.get("generated_assets"), dict) else {"characters": [], "scenes": []},
        "source": "episode_outline" if artifact else script_scope.get("source", "missing"),
    }
```

Because `_episode_dict_with_video_run` currently has no `db` argument, change the call site in `get_series` so the payload can attach `asset_scope` after `_episode_dict_with_video_run(e, active_run)`:

```python
episode_payload = _episode_dict_with_video_run(e, active_runs.get(e.id))
episode_payload["asset_scope"] = _episode_asset_scope_payload(db, e)
```

- [ ] Run the API test and confirm it passes.

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_series_api.py -q
```

- [ ] Add failing Vue test for episode asset display.

Expected UI text:

- `本集角色`
- `本集场景`
- `本集新增资产`
- `缺少本集角色或场景`

- [ ] Update `web/src/views/SeriesDetailPage.vue`.

Add compact blocks inside each expanded episode row:

```vue
<div class="grid gap-3 sm:grid-cols-2">
  <section class="rounded border border-slate-700/70 bg-slate-950/40 p-3">
    <h4 class="text-xs font-semibold text-slate-300">本集角色</h4>
    <div v-if="episodeAssetCharacters(ep).length" class="mt-2 flex flex-wrap gap-2">
      <span
        v-for="character in episodeAssetCharacters(ep)"
        :key="character.id"
        class="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200"
      >
        {{ character.name || character.id }}
        <span v-if="character.source === 'generated'" class="ml-1 text-emerald-300">新增</span>
      </span>
    </div>
    <p v-else class="mt-2 text-xs text-amber-300">缺少本集角色</p>
  </section>
  <section class="rounded border border-slate-700/70 bg-slate-950/40 p-3">
    <h4 class="text-xs font-semibold text-slate-300">本集场景</h4>
    <div v-if="episodeAssetScenes(ep).length" class="mt-2 flex flex-wrap gap-2">
      <span
        v-for="scene in episodeAssetScenes(ep)"
        :key="scene.id"
        class="rounded bg-slate-800 px-2 py-1 text-xs text-slate-200"
      >
        {{ scene.name || scene.id }}
        <span v-if="scene.source === 'generated'" class="ml-1 text-emerald-300">新增</span>
      </span>
    </div>
    <p v-else class="mt-2 text-xs text-amber-300">缺少本集场景</p>
  </section>
</div>
<p v-if="episodeAssetMissing(ep)" class="mt-2 text-xs text-amber-300">缺少本集角色或场景</p>
```

Add script helpers:

```js
function episodeAssetCharacters(ep) {
  return Array.isArray(ep?.asset_scope?.characters) ? ep.asset_scope.characters : []
}

function episodeAssetScenes(ep) {
  return Array.isArray(ep?.asset_scope?.scenes) ? ep.asset_scope.scenes : []
}

function episodeAssetMissing(ep) {
  return !episodeAssetCharacters(ep).length || !episodeAssetScenes(ep).length
}
```

- [ ] Run the Vue tests.

```powershell
Set-Location web
npx vitest run src/__tests__/series-detail-agency.test.js
Set-Location ..
```

- [ ] Commit only API/UI changes.

```powershell
git add server/app/routers/series.py server/tests/test_series_api.py web/src/views/SeriesDetailPage.vue web/src/__tests__/series-detail-agency.test.js
git commit -m "feat: show per-episode assets in series detail"
```

## Task 7: End-to-End Regression

**Files:**

- No new source files unless a focused fix is required by a failing test from this task.

**Success criteria:**

- Backend tests covering story planning, script generation, storyboard frame metadata, production readiness, and series API pass together.
- Frontend tests covering series detail still pass.
- If the backend server is running locally, the series detail page loads and displays episode asset scope without console errors.

**Steps:**

- [ ] Run the backend regression set.

```powershell
server\.venv\Scripts\python.exe -m pytest `
  server/tests/test_episode_asset_scope_service.py `
  server/tests/test_series_planning_service.py `
  server/tests/test_script_pipeline.py `
  server/tests/test_video_production_start_flow_contract.py `
  server/tests/test_series_api.py `
  -q
```

- [ ] Run the frontend regression set.

```powershell
Set-Location web
npx vitest run src/__tests__/series-detail-agency.test.js src/__tests__/api-clients.test.js
Set-Location ..
```

- [ ] Inspect the final diff to ensure only the planned files changed.

```powershell
git status --short
git diff -- server/app/services/episode_asset_scope_service.py server/app/services/series_planning_service.py server/app/services/story_generator_expert.py server/app/models/script.py server/app/services/script_pipeline.py server/app/services/production_errors.py server/app/services/production_run_service.py server/app/routers/series.py server/tests/test_episode_asset_scope_service.py server/tests/test_series_planning_service.py server/tests/test_script_pipeline.py server/tests/test_video_production_start_flow_contract.py server/tests/test_series_api.py web/src/views/SeriesDetailPage.vue web/src/__tests__/series-detail-agency.test.js
```

- [ ] Save a concise EverCore memory note after implementation succeeds.

```powershell
.\tools\evercore-memory.ps1 save "Implemented per-episode asset scopes: story planning normalizes character/scene usage, script/storyboard/production carry IDs, series detail exposes episode asset summaries." -BaseUrl "http://localhost:1995" -GroupId "dy_auto"
```

## Verification Checklist

- [ ] `episode_outline.character_ids` and `episode_outline.scene_ids` are never empty after story planning completes.
- [ ] `episode_outline.asset_usage` records names, usage, and `existing|generated|fallback` source.
- [ ] Generated assets are persisted as `Character` / `Scene` rows and linked to the series.
- [ ] Script prompts place "本集资产清单" before broader series continuity context.
- [ ] `episode.script_json.episode_asset_scope` is written.
- [ ] Every script-pipeline storyboard frame has `scene_id` and `character_ids`.
- [ ] Production refuses episodes with no usable episode or frame asset scope.
- [ ] Series detail UI distinguishes series-level assets from per-episode assets.
