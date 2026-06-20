# Storyboard Frame Image Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a complete storyboard frame image loop: generate image tasks from timed storyboard frames, show/review the linked image assets, promote approved assets into video production, and make video generation prefer those approved frame images.

**Architecture:** Reuse existing `ImageCreationTask`, `ImageCreationAsset`, image review gates, and `promote_image_asset_to_video_asset`. Add a thin storyboard-image orchestration service and router; frontend pages call that API and keep existing image creation/review systems as the source of truth.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Vitest, existing dy_auto image creation and video production services.

---

## File Structure

- Create `server/app/services/storyboard_image_service.py`: resolves episode/run storyboard frames, builds image creation payloads, creates per-frame/batch tasks, lists frame image state, and promotes reviewed image assets.
- Create `server/app/routers/storyboard_images.py`: exposes `/api/storyboard-images/...` endpoints with admin auth.
- Modify `server/app/main.py`: register the new router.
- Modify `server/app/services/video_production_service.py`: enrich image-stage frame payloads with approved promoted storyboard image source URLs when present.
- Create `server/tests/test_storyboard_image_service.py`: service-level unit tests with patched image creation calls.
- Create `server/tests/test_storyboard_images_api.py`: API contract tests through `TestClient`.
- Modify `server/tests/test_video_production_service.py` or create `server/tests/test_storyboard_image_video_bridge.py`: verifies promoted storyboard images are preferred by image/video stage payloads.
- Create `web/src/api/storyboardImages.js`: client helpers.
- Modify `web/src/views/SeriesDetailPage.vue`: show per-frame image status/actions in the storyboard section.
- Modify `web/src/views/VideoProductionMonitorPage.vue`: show run-level storyboard image readiness and promotion action.
- Add/update frontend tests in `web/src/__tests__/series-detail-agency.test.js`, `web/src/__tests__/series-detail-video-production.test.js`, and `web/src/__tests__/video-production-monitor-page.test.js`.

---

### Task 1: Backend Storyboard Image Service

**Files:**
- Create: `server/app/services/storyboard_image_service.py`
- Test: `server/tests/test_storyboard_image_service.py`

- [ ] **Step 1: Write failing service tests**

Add tests that construct a series, episode with two timed storyboard frames, and a production run. Patch `app.services.storyboard_image_service.create_image_task` to capture payloads and return lightweight task objects.

Expected assertions:

```python
assert captured["mode"] == "text_to_image"
assert captured["destination_role"] == "storyboard_frame"
assert captured["destination_context"]["frame_id"] == "shot-001"
assert captured["destination_context"]["time_range"] == "0-2秒"
assert captured["reference_images"][0]["url"] == "/static/characters/laoli-front.png"
assert captured["idempotency_key"].startswith("storyboard-frame-image:")
```

Also assert:

```python
assert result["frame_id"] == "shot-001"
assert result["task"]["id"] == "task-shot-001"
assert batch["summary"]["created"] == 2
assert listed["frames"][0]["frame_id"] == "shot-001"
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_image_service.py -q
```

Expected: import failure for `app.services.storyboard_image_service` or missing function errors.

- [ ] **Step 3: Implement the service**

Implement these functions:

```python
async def create_storyboard_frame_image_task(db, *, series_id, episode_id, frame_id, run_id=None, force=False, count=1, size=None, user_id=None) -> dict: ...
async def create_missing_storyboard_image_tasks(db, *, series_id, episode_id, run_id=None, force=False, count=1, size=None, user_id=None) -> dict: ...
def list_storyboard_image_state(db, *, series_id, episode_id, run_id=None) -> dict: ...
def promote_storyboard_image_asset(db, *, asset_id, run_id, frame_id, episode_id=None, asset_version=None, user_id=None) -> dict: ...
```

Core payload:

```python
payload = {
    "mode": "text_to_image",
    "prompt": frame["image_prompt"],
    "negative_prompt": frame.get("negative_prompt") or "",
    "reference_images": reference_images,
    "destination_role": "storyboard_frame",
    "destination_context": {
        "series_id": series_id,
        "episode_id": episode_id,
        "run_id": run_id or "",
        "frame_id": normalized_frame_id,
        "time_range": frame.get("time_range") or "",
        "source": "storyboard_image",
    },
    "series_id": series_id,
    "episode_id": episode_id,
    "count": count,
    "size": size,
    "idempotency_key": computed_key,
}
```

Frame lookup must accept `frame_id`, `shot_id`, and fallback `frame-001` ids. Missing frames raise `image_error(404, "STORYBOARD_FRAME_NOT_FOUND", ...)`. Empty prompts raise `image_error(422, "STORYBOARD_IMAGE_PROMPT_MISSING", ...)`.

- [ ] **Step 4: Run service tests**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_image_service.py -q
```

Expected: all service tests pass.

---

### Task 2: Storyboard Images API

**Files:**
- Create: `server/app/routers/storyboard_images.py`
- Modify: `server/app/main.py`
- Test: `server/tests/test_storyboard_images_api.py`

- [ ] **Step 1: Write failing API tests**

Tests should call:

```python
client.post(f"/api/storyboard-images/episodes/{episode.id}/frames/shot-001/tasks", json={"series_id": series.id})
client.post(f"/api/storyboard-images/episodes/{episode.id}/tasks:batch", json={"series_id": series.id})
client.get(f"/api/storyboard-images/episodes/{episode.id}", params={"series_id": series.id})
client.post(f"/api/storyboard-images/assets/{asset.id}/promote", json={"run_id": run.id, "frame_id": "shot-001", "asset_version": 1})
```

Expected responses:

```python
assert resp.status_code == 200
assert resp.json()["ok"] is True
assert resp.json()["frame"]["frame_id"] == "shot-001"
```

- [ ] **Step 2: Run API tests and see them fail**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_images_api.py -q
```

Expected: 404 route failures.

- [ ] **Step 3: Implement router and registration**

Router prefix:

```python
router = APIRouter(prefix="/api/storyboard-images", tags=["storyboard-images"])
```

Register in `server/app/main.py`:

```python
from app.routers import storyboard_images
app.include_router(storyboard_images.router)
```

Use Pydantic request models with fields `series_id`, `run_id`, `force`, `count`, `size`, `asset_version`, and `frame_id`.

- [ ] **Step 4: Run API tests**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_images_api.py -q
```

Expected: all API tests pass.

---

### Task 3: Video Production Bridge

**Files:**
- Modify: `server/app/services/video_production_service.py`
- Test: `server/tests/test_storyboard_image_video_bridge.py`

- [ ] **Step 1: Write failing bridge tests**

Create a run with a storyboard frame and an approved promoted `VideoProductionAsset` whose metadata contains:

```python
{"source_image_asset_id": image_asset.id, "destination_role": "storyboard_frame"}
```

Assert the image-stage payload includes:

```python
assert frame_payload["source_image_url"] == "/static/image-creation/approved.png"
assert frame_payload["storyboard_image_asset_id"] == image_asset.id
assert frame_payload["reference_urls"]
```

Also assert a review-pending `ImageCreationAsset` without promotion is not used.

- [ ] **Step 2: Run bridge tests and see them fail**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_image_video_bridge.py -q
```

Expected: payload does not expose `source_image_url` yet.

- [ ] **Step 3: Implement deterministic lookup**

Add a helper near image-stage payload helpers:

```python
def _approved_video_image_assets_by_frame(db: Session, run: VideoProductionRun) -> dict[str, VideoProductionAsset]:
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.status == "approved",
    ).all()
    return {str(row.frame_id): row for row in rows if row.url}
```

In `build_image_stage_frames_for_segments`, attach:

```python
approved = approved_assets.get(segment.id) or approved_assets.get(str(shot.shot_id))
if approved:
    payload["source_image_url"] = approved.url
    payload["storyboard_image_asset_id"] = (approved.metadata_json or {}).get("source_image_asset_id")
```

For legacy `image_stage_frames`, apply the same by normalized `frame_id` when `db` is provided.

- [ ] **Step 4: Run bridge tests and relevant production tests**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_image_video_bridge.py server/tests/test_video_production_service.py -q
```

Expected: tests pass.

---

### Task 4: Frontend API Client

**Files:**
- Create: `web/src/api/storyboardImages.js`
- Test: `web/src/__tests__/api-clients.test.js`

- [ ] **Step 1: Write failing client tests**

Assert the helpers call these endpoints:

```javascript
createStoryboardFrameImageTask(episodeId, frameId, payload)
createMissingStoryboardImageTasks(episodeId, payload)
getStoryboardImageState(episodeId, params)
promoteStoryboardImageAsset(assetId, payload)
```

- [ ] **Step 2: Run client test**

Run:

```powershell
cd web; npm test -- api-clients.test.js --runInBand
```

Expected: missing module/function failure.

- [ ] **Step 3: Implement client helper**

```javascript
import client from './client.js'

export function createStoryboardFrameImageTask(episodeId, frameId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/frames/${frameId}/tasks`, payload)
}

export function createMissingStoryboardImageTasks(episodeId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/tasks:batch`, payload)
}

export function getStoryboardImageState(episodeId, params = {}) {
  return client.get(`/storyboard-images/episodes/${episodeId}`, { params })
}

export function promoteStoryboardImageAsset(assetId, payload) {
  return client.post(`/storyboard-images/assets/${assetId}/promote`, payload)
}
```

- [ ] **Step 4: Run client test**

Run:

```powershell
cd web; npm test -- api-clients.test.js --runInBand
```

Expected: test passes.

---

### Task 5: Series Detail Storyboard Image UI

**Files:**
- Modify: `web/src/views/SeriesDetailPage.vue`
- Test: `web/src/__tests__/series-detail-agency.test.js`

- [ ] **Step 1: Write failing UI test**

Mock `getStoryboardImageState` to return:

```javascript
{
  frames: [{
    frame_id: 'shot-001',
    time_range: '0-2秒',
    status: 'approved',
    asset: { id: 'asset-1', url: '/static/storyboard-1.png', status: 'approved', version: 1 },
  }]
}
```

Assert:

```javascript
expect(wrapper.text()).toContain('分镜图')
expect(wrapper.text()).toContain('已通过')
expect(wrapper.find('img[alt*="0-2秒"]').exists()).toBe(true)
```

Assert clicking `生成缺失分镜图` calls `createMissingStoryboardImageTasks`.

- [ ] **Step 2: Run failing test**

Run:

```powershell
cd web; npm test -- series-detail-agency.test.js --runInBand
```

Expected: no storyboard image UI yet.

- [ ] **Step 3: Implement compact UI**

Add state:

```javascript
const storyboardImageState = ref({})
const storyboardImageBusy = ref({})
```

Add helpers:

```javascript
function storyboardImageForFrame(ep, frame) {
  const state = storyboardImageState.value[ep.id]
  return state?.frames_by_id?.[frame.frame_id || frame.shot_id] || null
}
```

Add actions:

```javascript
async function loadStoryboardImages(ep) { ... }
async function generateFrameImage(ep, frame) { ... }
async function generateMissingFrameImages(ep) { ... }
```

Render thumbnail, status badge, and buttons inside each storyboard frame card.

- [ ] **Step 4: Run UI test**

Run:

```powershell
cd web; npm test -- series-detail-agency.test.js --runInBand
```

Expected: test passes.

---

### Task 6: Production Monitor Readiness UI

**Files:**
- Modify: `web/src/views/VideoProductionMonitorPage.vue`
- Test: `web/src/__tests__/video-production-monitor-page.test.js`

- [ ] **Step 1: Write failing monitor test**

Mock storyboard image state with one missing and one approved frame. Assert:

```javascript
expect(wrapper.text()).toContain('分镜图')
expect(wrapper.text()).toContain('缺失 1')
expect(wrapper.text()).toContain('已通过 1')
```

When an approved asset has `allowed_actions: ['promote_to_video_asset']`, assert clicking `使用为首帧` calls promote API.

- [ ] **Step 2: Run failing test**

Run:

```powershell
cd web; npm test -- video-production-monitor-page.test.js --runInBand
```

Expected: no readiness panel yet.

- [ ] **Step 3: Implement monitor panel**

Load storyboard image state when `run.episode_id` is present:

```javascript
const response = await getStoryboardImageState(run.value.episode_id, {
  series_id: run.value.series_id,
  run_id: run.value.id,
})
```

Render summary counts and per-frame promote buttons for approved assets.

- [ ] **Step 4: Run monitor test**

Run:

```powershell
cd web; npm test -- video-production-monitor-page.test.js --runInBand
```

Expected: test passes.

---

### Task 7: Verification And Business Closure Audit

**Files:**
- No new files unless a test reveals a missing contract.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_storyboard_image_service.py server/tests/test_storyboard_images_api.py server/tests/test_storyboard_image_video_bridge.py -q
```

Expected: all pass.

- [ ] **Step 2: Run relevant backend regression**

Run:

```powershell
server\.venv\Scripts\python.exe -m pytest server/tests/test_image_creation_api.py server/tests/test_image_production_migration.py server/tests/test_video_production_service.py server/tests/test_video_production_start_flow_contract.py -q
```

Expected: all pass.

- [ ] **Step 3: Run focused frontend tests**

Run:

```powershell
cd web; npm test -- api-clients.test.js series-detail-agency.test.js video-production-monitor-page.test.js --runInBand
```

Expected: all pass.

- [ ] **Step 4: Run completion checklist**

Verify against the spec:

```text
storyboard frame -> image task -> image asset -> review gate -> promotion -> video stage payload -> UI state
```

Evidence must include API response examples, test output, and file references for the service, router, video bridge, and UI.

---

## Self Review

- Every spec requirement maps to at least one task.
- No new table or provider-specific path is introduced.
- The service delegates provider execution to existing image creation code.
- Review gate bypass is explicitly tested.
- The frontend uses compact additions to existing pages instead of a new page.
- Normal legacy production remains compatible because storyboard images are preferred only when approved/promoted.
