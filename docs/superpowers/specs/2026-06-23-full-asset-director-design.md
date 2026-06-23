# Full Asset Director Design

Date: 2026-06-23

## Problem

The current multi-episode series flow still treats the series asset pool as the primary source of characters and scenes. That works for a short proof of concept, but it is too thin for a real series:

- A few series-level characters and scenes are reused across too many episodes.
- Episode-specific characters and locations are not reliably created from the actual episode script/storyboard needs.
- Existing assets do not carry clear enough ownership such as series, episode, recurring role, or one-off role.
- Repeated characters and locations need visual consistency, but one-off assets should not pollute the main recurring pool.

The system already has useful primitives: `episode_asset_scope`, `generated_assets`, approved AI text artifacts, style lock references, and storyboard frame `character_ids` / `scene_id`. This design adds one explicit orchestration stage on top: the full asset director.

## Goal

Add a full asset director stage that reads series context, episode outlines, scripts, and storyboards, then produces a complete asset plan:

- Which characters and scenes are required per episode.
- Which assets are recurring and must be reused.
- Which assets are episode-only and should be newly created.
- Which series and episode each asset belongs to.
- Which storyboard frames use which character IDs and scene ID.

## Non-Goals

- Do not replace the existing creative library tables.
- Do not build a separate asset marketplace or heavy tagging system.
- Do not require manual approval before every asset creation in the first implementation.
- Do not create a new UI-heavy asset editor before the backend plan is reliable.

## Current Evidence

- Series-level auto asset generation exists in `server/app/domains/ai_video_series/style_lock.py`.
- Per-episode scope exists in `episode_asset_scope_service.py` and supports `generated_assets`.
- Story/script generation passes `episode_asset_scope` into the script prompt in `production_run_service.py`.
- Production applies episode scope back onto storyboard frames with `_apply_episode_asset_scope_to_storyboard`.

So the shortest correct path is to add an asset director stage that owns the complete scope plan, then reuse these existing hooks.

## Architecture

### New Domain Service

Create `server/app/domains/ai_video_series/asset_director_service.py`.

Responsibilities:

- Load series, episodes, approved story artifacts, script artifacts, and storyboard artifacts.
- Build an asset director prompt.
- Ask the configured LLM for a structured `asset_director_plan`.
- Normalize the result.
- Match recurring entities to existing assets.
- Create missing episode-specific assets.
- Write the final per-episode `episode_asset_scope`.
- Update storyboard frames with `character_ids` and `scene_id`.

### New Artifact Type

Store the plan as an AI text artifact:

- `artifact_type`: `asset_director_plan`
- `target_type`: `series`
- `target_id`: series id
- `content_json`: full asset plan
- `source_type`: `asset_director`

Per-episode scopes continue using approved `episode_outline` content and script `episode_asset_scope`, but the asset director becomes the preferred source when available.

## Asset Classification

Each created or matched character/scene receives metadata in `meta_json`:

```json
{
  "series_id": "series-id",
  "episode_id": "episode-id-or-null",
  "asset_scope": "series_recurring",
  "asset_source": "asset_director",
  "asset_director_plan_id": "artifact-id"
}
```

Allowed `asset_scope` values:

- `series_recurring`: appears across multiple episodes and must stay visually consistent.
- `episode_only`: created for one episode.
- `guest`: character appears in one or a few episodes but is not core cast.
- `location_recurring`: location reused across episodes.

Allowed `asset_source` values:

- `asset_director`
- `script_extracted`
- `story_plan`
- `manual`
- `style_lock`

Existing assets keep their current fields. The metadata is additive.

## Asset Director Plan Schema

The LLM must return JSON:

```json
{
  "series_id": "series-id",
  "recurring_characters": [
    {
      "stable_key": "lead_doctor",
      "name": "角色名",
      "reuse_character_id": "existing-character-id-or-null",
      "asset_scope": "series_recurring",
      "episode_numbers": [1, 2, 3],
      "appearance_desc": "稳定外观",
      "outfit_desc": "稳定服装",
      "usage": "剧情用途"
    }
  ],
  "episode_assets": [
    {
      "episode_number": 1,
      "characters": [
        {
          "stable_key": "patient_ep1",
          "name": "角色名",
          "asset_scope": "episode_only",
          "reuse_character_id": null,
          "appearance_desc": "外观",
          "outfit_desc": "服装",
          "usage": "本集用途"
        }
      ],
      "scenes": [
        {
          "stable_key": "ep1_clinic_room",
          "name": "场景名",
          "asset_scope": "episode_only",
          "reuse_scene_id": null,
          "scene_type": "indoor",
          "location_desc": "地点描述",
          "lighting": "warm_indoor",
          "mood": "tense",
          "usage": "本集用途"
        }
      ],
      "frame_bindings": [
        {
          "frame_id": "frame-001",
          "scene_stable_key": "ep1_clinic_room",
          "character_stable_keys": ["lead_doctor", "patient_ep1"]
        }
      ]
    }
  ]
}
```

## Matching Rules

Use deterministic matching before creating new assets:

1. If `reuse_character_id` or `reuse_scene_id` is present and linked to the series, reuse it.
2. Else match by normalized name within the same series.
3. Else match by `stable_key` stored in `meta_json`.
4. Else create a new asset.

If two existing assets match the same requested entity, fail the plan with a repairable error instead of guessing.

## Flow

### Story Planning

Story planning remains responsible for episode outlines and rough asset hints. It should not try to fully solve every asset.

### Script and Storyboard Draft

Generate script/storyboard draft from story context. The draft may include names and scene descriptions without finalized asset IDs.

### Asset Director

Run asset director after draft text exists:

1. Collect series asset pool.
2. Collect episode outline.
3. Collect script and storyboard draft.
4. Generate `asset_director_plan`.
5. Match or create assets.
6. Write per-episode scope.
7. Bind storyboard frames to final IDs.

### Production Start

`start_episode_production` must require asset director output when real production asks for prepared text artifacts. If missing, it runs the director or returns a repairable error.

## UI Changes

Minimal first version:

- Series detail shows an `资产导演` status row.
- Episode expanded panel shows each asset with classification:
  - recurring
  - episode only
  - guest
  - recurring location
- AI text workbench includes `asset_director_plan` artifacts.

No new full editor is required for the first implementation.

## Error Handling

Repairable errors:

- Asset director output is invalid JSON.
- An asset references an episode that does not exist.
- A requested reuse ID is not linked to the series.
- Multiple existing assets match the same requested stable entity.
- Storyboard frames cannot be bound to valid character and scene IDs.

Fallback:

- If the LLM fails before production, keep the run blocked and expose the repair route.
- Do not silently fall back to the whole series asset pool for real production.

## Testing

Backend tests:

- Creates episode-only character and scene from director plan.
- Reuses recurring character across multiple episodes.
- Stores `series_id`, `episode_id`, `asset_scope`, and `asset_source` in `meta_json`.
- Fails on ambiguous duplicate asset matches.
- Applies final `scene_id` and `character_ids` to storyboard frames.
- `start_episode_production(... prepare_text_artifacts=True)` refuses production if asset director output is missing or invalid.

Frontend tests:

- Series detail displays asset classifications per episode.
- AI text artifact workbench can list `asset_director_plan`.

## Acceptance Criteria

- A 30-episode series can have more than the initial 4 characters and 5 scenes.
- Repeated cast and recurring locations reuse the same asset IDs.
- Episode-only assets are created and tagged with their episode.
- Every production storyboard frame has a valid `scene_id` and `character_ids`.
- Real production does not use the full series asset pool as a silent fallback.
