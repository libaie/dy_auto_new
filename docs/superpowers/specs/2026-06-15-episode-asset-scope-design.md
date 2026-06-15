# Episode Asset Scope Design

Date: 2026-06-15

## Goal

Make series drama generation stricter by giving every episode its own character and scene usage set, generated from story/script needs rather than copied from the initial series-level asset pool.

The target outcome is:

- each episode has explicit linked characters and linked scenes;
- those links are created from the episode story/script intent;
- newly required characters or scenes are created as reusable assets and linked back to the series;
- script, storyboard, and production planning consume the episode-specific links before falling back to broader series assets.

## Current Behavior

The project already has three related layers:

- global asset rows: `Character` and `Scene`;
- series asset pool: `series_characters` and `series_scenes`;
- production-level usage: `ProductionScene.scene_id` and `ProductionShot.character_ids`.

Story planning artifacts also contain `episode_outline.character_ids` and `episode_outline.scene_ids`, but the current implementation usually derives those IDs from `style_lock` or the whole `series.characters` / `series.scenes` relation. That means every episode can inherit the same broad asset list even when the story needs a different cast or location set.

This is not strict enough for multi-episode series. A full series needs both reusable continuity assets and episode-specific usage decisions.

## Approved Direction

Use a "series asset pool + episode usage set + shot-level placement" model.

Series asset pool:

- owns reusable characters and scenes for the whole work;
- keeps visual identity and anchor reuse stable across episodes;
- continues to use existing `series_characters` and `series_scenes`.

Episode usage set:

- records the characters and scenes actually used by one episode;
- is generated from `episode_outline` and refined by script/storyboard generation;
- must never be empty for a production-ready episode.

Shot-level placement:

- remains the most specific layer;
- each storyboard frame and production shot should carry `character_ids` and `scene_id`;
- production uses the episode usage set as the allowed/default source, then narrows per shot.

## Data Contract

The first implementation should store episode usage inside the existing episode story artifacts and snapshots, avoiding a migration unless implementation proves query pressure requires one.

`episode_outline` should include:

```json
{
  "character_ids": ["character-id"],
  "scene_ids": ["scene-id"],
  "asset_usage": {
    "characters": [
      {
        "id": "character-id",
        "name": "角色名",
        "usage": "本集剧情作用",
        "source": "existing|generated|fallback"
      }
    ],
    "scenes": [
      {
        "id": "scene-id",
        "name": "场景名",
        "usage": "本集剧情作用",
        "source": "existing|generated|fallback"
      }
    ]
  },
  "generated_assets": {
    "characters": [],
    "scenes": []
  }
}
```

`episode.script_json` should copy the final episode usage set under:

```json
{
  "episode_asset_scope": {
    "character_ids": ["character-id"],
    "scene_ids": ["scene-id"],
    "source": "episode_outline|script_analysis|fallback"
  }
}
```

`episode.storyboard_json.frames[]` should include:

```json
{
  "scene_id": "scene-id",
  "character_ids": ["character-id"]
}
```

If later UI/API queries need a stable relational source, add `episode_characters` and `episode_scenes` as a follow-up migration. The initial contract should not block on that migration.

## Generation Flow

Story planning:

1. Ensure episode placeholders exist.
2. Provide the story generator with the current series asset pool and existing approved artifacts.
3. Require each `episode_outline` to choose the characters and scenes needed for that episode.
4. Allow the story generator to propose new characters/scenes when the episode requires assets not present in the pool.
5. Normalize generated assets into real `Character` and `Scene` rows.
6. Link newly created assets into `series_characters` / `series_scenes`.
7. Write the resulting IDs into the episode outline.

Script generation:

1. Load the approved `series_story_plan`, `season_arc`, and current `episode_outline`.
2. Resolve the episode usage set from `episode_outline.character_ids` and `episode_outline.scene_ids`.
3. Pass only the current episode's assets as primary context.
4. Include the broader series asset pool only as secondary continuity context.
5. Store the final usage set in `episode.script_json.episode_asset_scope`.

Storyboard generation:

1. Use the episode usage set as allowed/default assets.
2. Require every frame to include `scene_id` and `character_ids`.
3. If a frame omits IDs, infer from the current scene outline or episode usage set.
4. If inference is ambiguous, mark the pipeline blocked with a clear missing-asset error instead of silently producing generic frames.

Production planning:

1. `ProductionScene.scene_id` should come from storyboard frame `scene_id`.
2. `ProductionShot.character_ids` should come from storyboard frame `character_ids`.
3. Anchor composition should continue to use `AssetPromptCompositor`, but now the upstream IDs are episode-accurate.

## Asset Creation Rules

Generated character fields:

- `name`
- `role_type`
- `gender`
- `age_range`
- `personality`
- `appearance_desc`
- `outfit_desc`
- `meta_json.source = "episode_story_planning"`
- `meta_json.generated_for_episode_id`

Generated scene fields:

- `name`
- `scene_type`
- `location_desc`
- `lighting`
- `mood`
- `meta_json.source = "episode_story_planning"`
- `meta_json.generated_for_episode_id`

Deduplication:

- prefer existing assets when the generated name and role/location are clearly the same;
- never create duplicate main protagonists for each episode;
- create a new asset when the story introduces a genuinely new supporting role or location.

Human edits:

- preserve human-approved `episode_outline` artifacts unless `force=true`;
- if a human outline references valid assets, keep those IDs;
- if a human outline references missing assets, surface a validation error before production.

## UI Behavior

Series detail should show two levels:

- series asset pool: all reusable characters and scenes linked to the series;
- per-episode assets: the characters and scenes actually used in each episode.

Each episode card should display compact sections:

- "本集角色"
- "本集场景"
- "本集新增资产" when generated assets were created by story planning
- warning copy when an episode has no linked characters or scenes

The UI should not imply that the broad series asset pool equals the current episode's actual cast or location set.

## Error Handling

Missing episode usage:

- if the episode outline has no `character_ids` or no `scene_ids`, attempt fallback from the main series protagonist and primary scene;
- record fallback source in `asset_usage`;
- if fallback still cannot produce both a character and a scene, block production with a stable error code.

Invalid IDs:

- remove duplicate IDs;
- reject IDs that do not exist;
- reject IDs not linked to the series unless the normalizer created and linked them in the same planning run.

AI generation failure:

- deterministic fallback creates at least one character and one scene when the series asset pool is empty;
- fallback marks `source = "fallback"`;
- fallback trace remains visible in `model_trace_json`.

## API and Services

Primary service addition:

- add an episode asset normalizer in `series_planning_service.py` or a focused helper module.

Responsibilities:

- normalize `episode_outline.character_ids` and `scene_ids`;
- create new `Character` / `Scene` rows from generated asset specs;
- link new assets to the series;
- validate that every target episode has at least one character and one scene;
- expose normalized usage in the approved `episode_outline`.

Existing endpoints can remain:

- `POST /api/series/{series_id}/story-plan`
- `POST /api/series/{series_id}/episodes/{episode_id}/script`
- episode production start endpoints

Series detail response should include episode outline asset summaries so the frontend can display per-episode assets without issuing many extra requests.

## Testing

Backend tests:

- story planning creates distinct per-episode `character_ids` and `scene_ids`;
- story planning creates and links new assets proposed by the story generator;
- fallback creates minimal assets when the series pool is empty;
- human-approved episode outlines preserve their explicit asset IDs;
- invalid asset IDs block production or planning finalization with a clear error;
- script generation consumes current episode assets as primary context;
- storyboard frames persist `scene_id` and `character_ids`;
- production plan transfers frame IDs into `ProductionScene.scene_id` and `ProductionShot.character_ids`.

Frontend tests:

- series detail shows series asset pool separately from each episode asset set;
- episode cards display "本集角色" and "本集场景";
- missing episode assets show a warning;
- generated episode assets are labeled as newly created.

## Non-Goals

- Do not generate full second-by-second storyboards for every episode during story planning.
- Do not make `Character` or `Scene` private to one episode.
- Do not duplicate recurring protagonists per episode.
- Do not redesign the full series page layout.
- Do not require a database migration in the first implementation unless tests show artifact-backed lookup is insufficient.

## Acceptance Criteria

- Every generated or production-ready episode has non-empty `character_ids` and `scene_ids`.
- Episode asset IDs are based on the episode story/script, not blindly copied from the full series asset pool.
- New story-required characters/scenes are persisted as assets and linked to the series.
- Script generation uses episode-specific assets as primary context.
- Storyboard frames and production plans carry frame-level asset IDs.
- UI makes the difference between series asset pool and episode usage set visible.
