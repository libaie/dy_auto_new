# Asset Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add locked character and scene anchors so image/video generation can reuse stable faces, clothing, environments, references, and seeds.

**Architecture:** Keep the existing Character/Scene asset library as the source of identity data, and add a small anchor layer that links to those rows. `AssetAnchorManager` creates or updates anchors through the existing reference image pipeline, while `AssetPromptCompositor` builds shot payloads for production stages.

**Tech Stack:** FastAPI service layer, SQLAlchemy ORM, Pydantic V2, Alembic, pytest.

---

### Task 1: Models and Schema

**Files:**
- Create: `server/app/models/asset_anchor.py`
- Modify: `server/app/models/__init__.py`
- Modify: `server/app/db_models.py`
- Create: `server/alembic/versions/1b2c3d4e5f60_add_asset_anchor_tables.py`
- Test: `server/tests/test_asset_anchor_models.py`

- [x] Write tests for Pydantic validation and SQLAlchemy table columns.
- [x] Add `CharacterAnchor` and `SceneAnchor` ORM tables linked to `characters` and `scenes`.
- [x] Add Pydantic V2 DTOs for anchor records, reference modes, provider requests, and composed prompts.
- [x] Run `pytest server/tests/test_asset_anchor_models.py -q`.

### Task 2: Anchor Manager

**Files:**
- Create: `server/app/services/anchor_service.py`
- Test: `server/tests/test_anchor_service.py`

- [x] Write tests for character/scene anchor creation, existing slot reuse, provider adaptation, and seed filtering.
- [x] Reuse `reference_asset_service.generate_reference_url` only when the existing reference URL is missing or unusable.
- [x] Persist anchor prompts, image URLs, seed, provider reference metadata, and status.
- [x] Run `pytest server/tests/test_anchor_service.py -q`.

### Task 3: Prompt Compositor

**Files:**
- Create: `server/app/utils/__init__.py`
- Create: `server/app/utils/prompt_compositor.py`
- Test: `server/tests/test_prompt_compositor.py`

- [x] Write tests for strict prompt order: scene environment, character base prompt, shot action/emotion.
- [x] Add reference role payloads for character and scene anchors.
- [x] Add seed/provider option output and Wan 2.7 image-to-video input validation.
- [x] Run `pytest server/tests/test_prompt_compositor.py -q`.

### Task 4: Production Stage Integration

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/services/pixelle_execution_service.py`
- Modify: `server/tests/conftest.py`
- Test: targeted existing production tests plus new compositor tests.

- [x] Enrich linked image frames with composed prompts, typed reference roles, reference URLs, and provider options.
- [x] Enrich linked video frames with `input_image_url` alongside existing `approved_image_url`.
- [x] Keep legacy/storyboard runs unchanged.
- [x] Run targeted tests.
