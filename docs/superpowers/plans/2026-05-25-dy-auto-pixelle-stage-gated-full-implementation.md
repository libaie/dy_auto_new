# dy_auto Pixelle Stage-Gated Full Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the full dy_auto + Pixelle-Video stage-gated AI video production flow from storyboard to image review, video segment review, final composition, and dy_auto video library persistence.

**Architecture:** dy_auto remains the orchestration and truth layer for production state, review gates, model configuration, assets, and video library records. Pixelle-Video remains the execution layer behind explicit stage APIs for image generation, image-to-video segment rendering, and final composition. The implementation extends the current Phase 0/image wedge instead of replacing it.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic, httpx, pytest, Vue 3, Vue Router, Vitest, Pixelle-Video FastAPI task manager.

---

## Scope

This plan implements the full design in:

`D:\devWorkspace\jsProjects\dy_auto\docs\superpowers\specs\2026-05-25-dy-auto-pixelle-stage-gated-integration-design.md`

It assumes the current repository already has a partial Phase 0 + image-stage wedge:

- dy_auto has `VideoProductionRun`, `VideoProductionAsset`, `VideoReviewRecord`.
- dy_auto has image-stage create/start/sync/review routes.
- Pixelle-Video has `/api/stages/images/batch` and `/api/stages/tasks/{id}`.
- The review center exists but is still image-centric and thin.

This plan completes the missing production loop:

```text
storyboard
  -> batch image generation
  -> image AI review
  -> human image exception review
  -> batch image-to-video generation
  -> video segment AI review
  -> human video exception review
  -> final composition
  -> final audit gate
  -> Episode + GeneratedVideo library writeback
```

## Success Criteria

- `POST /api/video-production/runs/{run_id}/start-videos` refuses to run until every storyboard frame has a latest approved image asset.
- `POST /api/video-production/runs/{run_id}/sync-video-results` saves video segment assets, runs AI review, and advances or blocks the run.
- `POST /api/video-production/runs/{run_id}/compose` refuses to run until every frame has a latest approved video segment.
- `POST /api/video-production/runs/{run_id}/sync-compose-results` saves the final video asset; final audit approval or later human approval writes `Episode.video_url`, `Episode.duration_seconds`, `Episode.status`, and creates or updates `GeneratedVideo`.
- Review center can inspect image, video segment, and final video review items with prompt, narration, references, model trace, AI review records, and version history.
- Single image and single video segment regeneration preserve previous versions and re-run AI review for the new version.
- Pixelle stage API tests run without requiring a full `comfykit` runtime for contract, auth, and file-safety checks.
- Full mocked local E2E passes without paid providers.

## File Map

### dy_auto Backend

| File | Action | Responsibility |
|---|---|---|
| `server/app/services/video_production_state.py` | Create | Central state machine, latest-version invariants, run-level gate recomputation. |
| `server/app/services/video_production_service.py` | Modify | Delegate state decisions to `video_production_state.py`; add video stage, compose stage, regeneration orchestration, final writeback. |
| `server/app/services/pixelle_stage_client.py` | Modify | Add `submit_video_batch`, `submit_compose`, and one-item regeneration helpers. |
| `server/app/routers/video_production.py` | Modify | Add start/sync/approve APIs for video and compose stages; enrich review payloads. |
| `server/app/db_models.py` | Modify if needed | Add indexes only if migration shows missing query support. No new table unless current model cannot represent a field. |
| `server/alembic/versions/<new>_video_production_stage_indexes.py` | Create if needed | Add indexes for run/stage/status/version queries. |
| `server/tests/test_video_production_state_machine.py` | Create | State transitions, latest approved gate, idempotency, stale review conflicts. |
| `server/tests/test_video_production_video_stage.py` | Create | Video batch start/sync and AI review behavior. |
| `server/tests/test_video_production_compose.py` | Create | Compose start/sync, final asset persistence, `GeneratedVideo` writeback. |
| `server/tests/test_video_production_regeneration.py` | Create | Image and video segment regeneration preserving versions and gates. |
| `server/tests/test_video_production_full_mocked_e2e.py` | Create | Storyboard to final video mocked E2E. |
| `server/tests/test_pixelle_stage_client.py` | Modify | Cover image, video, compose stage client payloads. |
| `server/tests/test_video_production_api.py` | Modify | Cover new route contracts and review payloads. |

### dy_auto Frontend

| File | Action | Responsibility |
|---|---|---|
| `web/src/api/videoProduction.js` | Modify | Add video/compose start/sync APIs, enriched run/review helpers. |
| `web/src/views/AIVideoReviewPage.vue` | Modify or split | Show image, video segment, and final video review queues; show context and actions. |
| `web/src/views/VideoProductionMonitorPage.vue` | Create | Stage-gated production progress page for `VideoProductionRun`. |
| `web/src/views/SeriesDetailPage.vue` | Modify | Start staged production into monitor, show status strip, link to review center. |
| `web/src/router/index.js` | Modify | Add `/video-production/:runId` route if monitor is split from legacy pipeline. |
| `web/src/__tests__/ai-video-review-page.test.js` | Modify | Cover multi-stage review, context panels, approve/reject/regenerate. |
| `web/src/__tests__/video-production-monitor-page.test.js` | Create | Cover stage strip, automatic sync prompts, blocked states. |
| `web/src/__tests__/series-detail-video-production.test.js` | Modify | Start flow routes to production monitor and review center when blocked. |
| `web/src/__tests__/api-clients.test.js` | Modify | Cover added client methods. |

### Pixelle-Video

| File | Action | Responsibility |
|---|---|---|
| `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py` | Modify | Add video batch and compose request/response schemas. |
| `D:\devWorkspace\Pixelle-Video\api\routers\stages.py` | Modify | Add `/videos/batch`, `/compose`, structured per-frame errors, and mock outputs. |
| `D:\devWorkspace\Pixelle-Video\api\services\stage_runtime_config.py` | Create | Apply dy_auto runtime model config to Pixelle stage execution without storing secrets. |
| `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py` | Create | Wrap existing Pixelle post-production composition primitives for stage `/compose`. |
| `D:\devWorkspace\Pixelle-Video\api\dependencies.py` | Modify | Make API tests able to import app without importing `comfykit` at module import time. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_api_auth.py` | Modify | Keep auth coverage runnable without `comfykit`. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_images_api.py` | Modify | Keep image stage tests runnable and assert mock file exists. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_runtime_config.py` | Create | Verify runtime model config is passed into real Pixelle provider calls and redacted from task payloads. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_videos_api.py` | Create | Video batch validation and mock segment output. |
| `D:\devWorkspace\Pixelle-Video\tests\test_stage_compose_api.py` | Create | Compose validation and mock final output. |
| `D:\devWorkspace\Pixelle-Video\tests\test_files_security.py` | Modify | Include sibling prefix regression such as `output_evil`. |

## Task 1: Make Pixelle Stage API Tests Independent of Full Runtime

**Files:**

- Modify: `D:\devWorkspace\Pixelle-Video\api\dependencies.py`
- Modify: `D:\devWorkspace\Pixelle-Video\tests\test_stage_api_auth.py`
- Modify: `D:\devWorkspace\Pixelle-Video\tests\test_stage_images_api.py`
- Modify: `D:\devWorkspace\Pixelle-Video\tests\test_files_security.py`

- [ ] **Step 1: Write failing import smoke test**

Add this test to `D:\devWorkspace\Pixelle-Video\tests\test_stage_api_auth.py`:

```python
def test_api_app_imports_without_comfykit_for_stage_contract_tests():
    from api.app import app

    routes = {route.path for route in app.routes}
    assert "/api/stages/images/batch" in routes
    assert "/api/stages/tasks/{stage_task_id}" in routes
```

- [ ] **Step 2: Run Pixelle stage tests and verify the current failure**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_files_security.py -q
```

Expected before implementation: FAIL during collection or import with `ModuleNotFoundError: No module named 'comfykit'`.

- [ ] **Step 3: Lazy-import `PixelleVideoCore` in dependencies**

Replace the top-level import of `PixelleVideoCore` in `D:\devWorkspace\Pixelle-Video\api\dependencies.py` with a lazy import inside `get_pixelle_video`.

Use this implementation shape:

```python
from typing import Annotated, Any

from fastapi import Depends
from loguru import logger

_pixelle_video_instance: Any = None


async def get_pixelle_video() -> Any:
    """Get Pixelle-Video core instance lazily so API contract tests do not need full render deps."""
    global _pixelle_video_instance
    if _pixelle_video_instance is None:
        from pixelle_video.service import PixelleVideoCore

        _pixelle_video_instance = PixelleVideoCore()
        await _pixelle_video_instance.initialize()
        logger.info("Pixelle-Video initialized for API")
    return _pixelle_video_instance


async def shutdown_pixelle_video():
    """Shutdown Pixelle-Video instance and cleanup resources."""
    global _pixelle_video_instance
    if _pixelle_video_instance:
        logger.info("Shutting down Pixelle-Video...")
        await _pixelle_video_instance.cleanup()
        _pixelle_video_instance = None


PixelleVideoDep = Annotated[Any, Depends(get_pixelle_video)]
```

If `shutdown_pixelle_video` currently imports `HTMLFrameGenerator`, keep that import inside the function branch that needs it, not at module import time.

- [ ] **Step 4: Run Pixelle stage tests**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_files_security.py -q
```

Expected: PASS. If a test needs Pixelle runtime behavior, override `app.dependency_overrides[get_pixelle_video]` inside that test with a fake object.

- [ ] **Step 5: Commit Pixelle runtime test decoupling**

```powershell
cd D:\devWorkspace\Pixelle-Video
git add api/dependencies.py tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_files_security.py
git commit -m "test: decouple stage API tests from Pixelle runtime"
```

## Task 2: Add Pixelle Video and Compose Stage Contracts

**Revision note:** This task depends on Task 2A. Do not implement the real provider branches until the runtime config adapter and compose adapter exist.

## Task 2A: Add Pixelle Runtime Config and Compose Adapters

**Files:**

- Create: `D:\devWorkspace\Pixelle-Video\api\services\stage_runtime_config.py`
- Create: `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_runtime_config.py`

- [ ] **Step 1: Write runtime config adapter tests**

Create `D:\devWorkspace\Pixelle-Video\tests\test_stage_runtime_config.py`:

```python
from api.services.stage_runtime_config import redact_stage_model_config, stage_media_kwargs


def test_stage_media_kwargs_maps_runtime_model_config():
    kwargs = stage_media_kwargs({
        "provider": "runninghub",
        "model": "doubao-seedance-2.0-260128",
        "api_key": "secret-key",
        "base_url": "https://runninghub.test",
        "config": {
            "default_workflow": "runninghub/video_seedance.json",
            "default_duration": 6,
            "default_resolution": "720p",
            "default_aspect_ratio": "9:16",
            "parameters": {"seed": 123, "cfg": 7.5},
        },
    }, media_type="video")

    assert kwargs["media_type"] == "video"
    assert kwargs["workflow"] == "runninghub/video_seedance.json"
    assert kwargs["runninghub_api_key"] == "secret-key"
    assert kwargs["comfyui_url"] == "https://runninghub.test"
    assert kwargs["model"] == "doubao-seedance-2.0-260128"
    assert kwargs["duration"] == 6
    assert kwargs["resolution"] == "720p"
    assert kwargs["aspect_ratio"] == "9:16"
    assert kwargs["seed"] == 123
    assert kwargs["cfg"] == 7.5


def test_stage_media_kwargs_accepts_dy_auto_resolve_runtime_model_config_shape():
    kwargs = stage_media_kwargs({
        "scene_key": "image_generation",
        "model_id": "model-1",
        "provider": "seedance",
        "model": "seedance-image",
        "base_url": "https://ark.test",
        "api_key": "secret-key",
        "config": {
            "scene_key": "image_generation",
            "default_workflow": "image_seedance.json",
            "default_resolution": "1080x1920",
            "parameters": {"steps": 20},
        },
    }, media_type="image")

    assert kwargs["workflow"] == "image_seedance.json"
    assert kwargs["resolution"] == "1080x1920"
    assert kwargs["width"] == 1080
    assert kwargs["height"] == 1920
    assert kwargs["steps"] == 20
    assert kwargs["runninghub_api_key"] == "secret-key"


def test_stage_model_config_redaction_is_recursive():
    redacted = redact_stage_model_config({
        "provider": "seedance",
        "api_key": "secret-key",
        "nested": {"api_secret": "secret-2", "safe": "value"},
    })

    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["nested"]["api_secret"] == "***REDACTED***"
    assert redacted["nested"]["safe"] == "value"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_runtime_config.py -q
```

Expected: FAIL because `api.services.stage_runtime_config` does not exist.

- [ ] **Step 3: Create runtime config adapter**

Create `D:\devWorkspace\Pixelle-Video\api\services\stage_runtime_config.py`:

```python
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

SECRET_KEYS = {"api_key", "api_secret", "secret", "token", "access_token", "runninghub_api_key", "comfyui_api_key"}


def redact_stage_model_config(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_stage_model_config(item)
        return redacted
    if isinstance(value, list):
        return [redact_stage_model_config(item) for item in value]
    return value


def stage_media_kwargs(model_config: dict[str, Any], media_type: str) -> dict[str, Any]:
    provider = model_config.get("provider", "")
    config = dict(model_config.get("config") or model_config.get("config_json") or {})
    nested_params = dict(config.get("parameters") or {})
    top_params = dict(model_config.get("parameters") or {})
    params = {**nested_params, **top_params}
    kwargs: dict[str, Any] = {
        "media_type": media_type,
        "workflow": (
            model_config.get("workflow")
            or model_config.get("default_workflow")
            or config.get("workflow")
            or config.get("default_workflow")
        ),
        "model": model_config.get("model") or model_config.get("model_name"),
        "provider": provider,
        "duration": model_config.get("duration") or config.get("duration") or config.get("default_duration"),
        "resolution": model_config.get("resolution") or config.get("resolution") or config.get("default_resolution"),
        "aspect_ratio": model_config.get("aspect_ratio") or config.get("aspect_ratio") or config.get("default_aspect_ratio"),
    }
    if model_config.get("base_url"):
        kwargs["comfyui_url"] = model_config["base_url"]
    if provider in {"runninghub", "seedance", "kling", "wan", "comfyui"} and model_config.get("api_key"):
        kwargs["runninghub_api_key"] = model_config["api_key"]
    kwargs.update({key: value for key, value in params.items() if value is not None})
    resolution = str(kwargs.get("resolution") or "")
    if "x" in resolution and "width" not in kwargs and "height" not in kwargs:
        width, height = resolution.lower().split("x", 1)
        if width.isdigit() and height.isdigit():
            kwargs["width"] = int(width)
            kwargs["height"] = int(height)
    return {key: value for key, value in kwargs.items() if value is not None}


@contextmanager
def apply_stage_runtime_config(pixelle_video: Any, model_config: dict[str, Any]):
    previous = getattr(pixelle_video, "_stage_runtime_model_config", None)
    pixelle_video._stage_runtime_model_config = redact_stage_model_config(model_config)
    try:
        yield
    finally:
        if previous is None:
            try:
                delattr(pixelle_video, "_stage_runtime_model_config")
            except AttributeError:
                pass
        else:
            pixelle_video._stage_runtime_model_config = previous
```

- [ ] **Step 4: Create compose adapter**

Create `D:\devWorkspace\Pixelle-Video\api\services\stage_compose.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pixelle_video.services.post_production import compose_final_video, get_video_info


def _local_segment_path(video_url: str) -> str:
    if video_url.startswith("/api/files/"):
        return str((Path.cwd() / "output" / video_url.removeprefix("/api/files/")).resolve())
    return video_url


async def compose_stage_video(request: Any, task_id: str) -> dict[str, Any]:
    output_path = str((Path.cwd() / "output" / task_id / "final.mp4").resolve())
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    manifest = request.edit_manifest or {}
    segments = [_local_segment_path(segment.video_url) for segment in request.segments]
    result_path = await compose_final_video(
        video_segments=segments,
        audio_paths=[],
        output_path=output_path,
        bgm_path=(manifest.get("bgm_policy") or {}).get("path", ""),
        bgm_volume=float((manifest.get("bgm_policy") or {}).get("volume", 0.18)),
        title_text=(manifest.get("intro_outro") or {}).get("title", ""),
        fps=int((manifest.get("output_spec") or {}).get("fps", 30)),
    )
    return {
        "local_path": result_path,
        "url": f"/api/files/{Path(result_path).relative_to(Path.cwd() / 'output').as_posix()}",
        "metadata": get_video_info(result_path),
    }
```

- [ ] **Step 5: Run adapter tests**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_runtime_config.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit runtime adapters**

```powershell
cd D:\devWorkspace\Pixelle-Video
git add api/services/stage_runtime_config.py api/services/stage_compose.py tests/test_stage_runtime_config.py
git commit -m "feat: add Pixelle stage runtime adapters"
```

**Files:**

- Modify: `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py`
- Modify: `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_videos_api.py`
- Create: `D:\devWorkspace\Pixelle-Video\tests\test_stage_compose_api.py`

- [ ] **Step 1: Write video stage tests**

Create `D:\devWorkspace\Pixelle-Video\tests\test_stage_videos_api.py`:

```python
import time

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import get_pixelle_video


class FakeMediaResult:
    def __init__(self, url: str):
        self.url = url


class FakePixelleVideo:
    async def media(self, prompt: str, **kwargs):
        return FakeMediaResult("/api/files/fake.mp4")


def client_with_fake_pixelle(monkeypatch) -> TestClient:
    monkeypatch.setattr("api.middleware.API_KEY", "test-key")
    monkeypatch.setitem(app.dependency_overrides, get_pixelle_video, lambda: FakePixelleVideo())
    return TestClient(app)


def wait_for_completed_stage(client: TestClient, stage_task_id: str, api_key: str = "test-key") -> dict:
    for _ in range(40):
        response = client.get(f"/api/stages/tasks/{stage_task_id}", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        body = response.json()
        if body["status"] == "completed":
            return body
        if body["status"] == "failed":
            raise AssertionError(body.get("error") or "Stage task failed")
        time.sleep(0.05)
    raise AssertionError("Stage task did not complete")


def test_video_batch_requires_frames(monkeypatch):
    client = client_with_fake_pixelle(monkeypatch)

    response = client.post(
        "/api/stages/videos/batch",
        headers={"X-API-Key": "test-key"},
        json={
            "external_run_id": "run-1",
            "frames": [],
            "model_config": {"provider": "mock", "model": "mock-video"},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "frames is required"


def test_video_batch_mock_creates_task_and_segment_assets(monkeypatch):
    client = client_with_fake_pixelle(monkeypatch)

    response = client.post(
        "/api/stages/videos/batch",
        headers={"X-API-Key": "test-key"},
        json={
            "external_run_id": "run-1",
            "frames": [
                {
                    "frame_id": "frame-001",
                    "approved_image_url": "/api/files/example.png",
                    "video_prompt": "slow push-in shot",
                    "reference_urls": ["https://cdn.test/ref.png"],
                    "duration": 5,
                    "audio_mode": "tts",
                }
            ],
            "model_config": {"provider": "mock", "model": "mock-video"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stage_task_id"]

    status_body = wait_for_completed_stage(client, body["stage_task_id"])
    assert status_body["assets"][0]["frame_id"] == "frame-001"
    assert status_body["assets"][0]["asset_type"] == "video_segment"
    assert status_body["assets"][0]["url"].endswith(".mp4")


def test_video_batch_records_per_frame_failure_without_failing_whole_task(monkeypatch):
    class FakePixelleVideo:
        async def media(self, prompt: str, **kwargs):
            if "bad" in prompt:
                raise RuntimeError("provider unavailable")
            return FakeMediaResult("/api/files/good.mp4")

    monkeypatch.setattr("api.middleware.API_KEY", "test-key")
    monkeypatch.setitem(app.dependency_overrides, get_pixelle_video, lambda: FakePixelleVideo())
    client = TestClient(app)
    response = client.post(
        "/api/stages/videos/batch",
        headers={"X-API-Key": "test-key"},
        json={
            "external_run_id": "run-1",
            "frames": [
                {"frame_id": "frame-001", "approved_image_url": "/api/files/one.png", "video_prompt": "good frame", "duration": 5},
                {"frame_id": "frame-002", "approved_image_url": "/api/files/two.png", "video_prompt": "bad frame", "duration": 5},
            ],
            "model_config": {"provider": "seedance", "model": "video-model"},
        },
    )

    assert response.status_code == 200
    status_body = wait_for_completed_stage(client, response.json()["stage_task_id"])
    by_frame = {asset["frame_id"]: asset for asset in status_body["assets"]}
    assert by_frame["frame-001"]["status"] == "generated"
    assert by_frame["frame-002"]["status"] == "failed"
    assert by_frame["frame-002"]["error_code"] == "VIDEO_RENDER_FAILED"
    assert by_frame["frame-002"]["retryable"] is True
```

- [ ] **Step 2: Write compose stage tests**

Create `D:\devWorkspace\Pixelle-Video\tests\test_stage_compose_api.py`:

```python
import time

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import get_pixelle_video


class FakePixelleVideo:
    pass


def client_with_fake_pixelle(monkeypatch) -> TestClient:
    monkeypatch.setattr("api.middleware.API_KEY", "test-key")
    monkeypatch.setitem(app.dependency_overrides, get_pixelle_video, lambda: FakePixelleVideo())
    return TestClient(app)


def wait_for_completed_stage(client: TestClient, stage_task_id: str, api_key: str = "test-key") -> dict:
    for _ in range(40):
        response = client.get(f"/api/stages/tasks/{stage_task_id}", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        body = response.json()
        if body["status"] == "completed":
            return body
        if body["status"] == "failed":
            raise AssertionError(body.get("error") or "Stage task failed")
        time.sleep(0.05)
    raise AssertionError("Stage task did not complete")


def test_compose_requires_segments(monkeypatch):
    client = client_with_fake_pixelle(monkeypatch)

    response = client.post(
        "/api/stages/compose",
        headers={"X-API-Key": "test-key"},
        json={
            "external_run_id": "run-1",
            "segments": [],
            "edit_manifest": {"output_spec": {"resolution": "1080x1920"}},
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "segments is required"


def test_compose_mock_creates_final_video_asset(monkeypatch):
    client = client_with_fake_pixelle(monkeypatch)

    response = client.post(
        "/api/stages/compose",
        headers={"X-API-Key": "test-key"},
        json={
            "external_run_id": "run-1",
            "segments": [
                {
                    "frame_id": "frame-001",
                    "video_url": "/api/files/segment.mp4",
                    "duration": 5,
                    "narration": "hello",
                }
            ],
            "edit_manifest": {
                "subtitle_style": {"font_size": 42},
                "bgm_policy": {"mode": "auto"},
                "intro_outro": {},
                "watermark": {},
                "output_spec": {"aspect_ratio": "9:16", "resolution": "1080x1920"},
            },
            "model_config": {"provider": "mock", "model": "mock-compose"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stage_task_id"]

    status_body = wait_for_completed_stage(client, body["stage_task_id"])
    assert status_body["assets"][0]["asset_type"] == "final_video"
    assert status_body["assets"][0]["url"].endswith(".mp4")
    assert status_body["assets"][0]["metadata"]["duration"] == 5
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_videos_api.py tests/test_stage_compose_api.py -q
```

Expected: FAIL because `VideoBatchRequest`, `ComposeRequest`, `/videos/batch`, and `/compose` are not implemented.

- [ ] **Step 4: Add schemas**

First, extend `StageAsset` in `D:\devWorkspace\Pixelle-Video\api\schemas\stages.py` so partial failures can be returned per frame:

```python
class StageAsset(BaseModel):
    frame_id: str
    asset_type: str
    url: str = ""
    local_path: str = ""
    status: str = "generated"
    error_code: str | None = None
    message: str | None = None
    retryable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Then append these classes to the same file:

```python
class StageFrameError(BaseModel):
    frame_id: str
    asset_type: str
    status: str = "failed"
    error_code: str
    message: str
    retryable: bool = True


class VideoStageFrame(BaseModel):
    frame_id: str
    approved_image_url: str
    video_prompt: str = ""
    reference_urls: list[str] = Field(default_factory=list)
    duration: float = 5.0
    audio_mode: str = "tts"


class VideoBatchRequest(BaseModel):
    external_run_id: str
    frames: list[VideoStageFrame]
    stage_model_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    template_config: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class ComposeSegment(BaseModel):
    frame_id: str
    video_url: str
    duration: float = 5.0
    narration: str = ""


class ComposeRequest(BaseModel):
    external_run_id: str
    segments: list[ComposeSegment]
    edit_manifest: dict[str, Any] = Field(default_factory=dict)
    stage_model_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")

    class Config:
        populate_by_name = True
```

- [ ] **Step 5: Add video and compose route imports**

Modify the import in `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`:

```python
from api.services.stage_compose import compose_stage_video
from api.services.stage_runtime_config import apply_stage_runtime_config, redact_stage_model_config, stage_media_kwargs
from api.schemas.stages import (
    ComposeRequest,
    ImageBatchRequest,
    StageAsset,
    StageFrameError,
    StageTaskResponse,
    StageTaskStatusResponse,
    VideoBatchRequest,
)
```

- [ ] **Step 5A: Update image batch to apply runtime model config**

In `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`, replace the non-mock branch inside `_run_image_batch` with:

```python
        else:
            media_kwargs = stage_media_kwargs(request.stage_model_config, media_type="image")
            media_kwargs.setdefault("width", int(request.template_config.get("width", 1080)))
            media_kwargs.setdefault("height", int(request.template_config.get("height", 1920)))
            with apply_stage_runtime_config(pixelle_video, request.stage_model_config):
                media_result = await pixelle_video.media(
                    prompt=frame.image_prompt,
                    **media_kwargs,
                )
            local_path = media_result.url
            url = media_result.url
```

- [ ] **Step 6: Add mock output helpers**

Add these helpers below `_MINIMAL_PNG` in `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`:

```python
import subprocess


def _write_mock_mp4(local_path: str) -> None:
    _ensure_dir(os.path.dirname(local_path))
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=160x90:r=24",
            "-t", "0.25",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            local_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Mock MP4 generation failed: {result.stderr}")
```

- [ ] **Step 7: Add video batch execution**

Add this function to `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`:

```python
async def _run_video_batch(request: VideoBatchRequest, pixelle_video: PixelleVideoDep, task_id: str) -> dict:
    assets = []
    total = max(len(request.frames), 1)
    for index, frame in enumerate(request.frames, start=1):
        task_manager.update_progress(task_id, index - 1, total, f"Rendering segment {frame.frame_id}")
        try:
            if request.stage_model_config.get("provider") == "mock":
                local_path = f"output/{task_id}/{frame.frame_id}.mp4"
                _write_mock_mp4(local_path)
                url = _public_file_url(local_path)
            else:
                media_kwargs = stage_media_kwargs(request.stage_model_config, media_type="video")
                media_kwargs.setdefault("width", int(request.template_config.get("width", 1080)))
                media_kwargs.setdefault("height", int(request.template_config.get("height", 1920)))
                media_kwargs.setdefault("duration", frame.duration)
                with apply_stage_runtime_config(pixelle_video, request.stage_model_config):
                    media_result = await pixelle_video.media(
                        prompt=frame.video_prompt or f"Animate image for {frame.duration} seconds",
                        image=frame.approved_image_url,
                        **media_kwargs,
                    )
                local_path = media_result.url
                url = media_result.url
            assets.append(StageAsset(
                frame_id=frame.frame_id,
                asset_type="video_segment",
                url=url,
                local_path=local_path,
                metadata={"duration": frame.duration, "audio_mode": frame.audio_mode},
            ).model_dump())
            task_manager.update_progress(task_id, index, total, f"Rendered segment {frame.frame_id}")
        except Exception as exc:
            error = StageFrameError(
                frame_id=frame.frame_id,
                asset_type="video_segment",
                error_code="VIDEO_RENDER_FAILED",
                message=str(exc),
                retryable=True,
            ).model_dump()
            assets.append(StageAsset(
                frame_id=frame.frame_id,
                asset_type="video_segment",
                status="failed",
                error_code=error["error_code"],
                message=error["message"],
                retryable=error["retryable"],
                metadata={"duration": frame.duration, "audio_mode": frame.audio_mode},
            ).model_dump())
            task_manager.update_progress(task_id, index, total, f"Failed segment {frame.frame_id}")
    return {"assets": assets}
```

- [ ] **Step 8: Add compose execution**

Add this function to `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`:

```python
async def _run_compose(request: ComposeRequest, pixelle_video: PixelleVideoDep, task_id: str) -> dict:
    total_duration = sum(segment.duration for segment in request.segments)
    task_manager.update_progress(task_id, 0, 1, "Composing final video")
    if request.stage_model_config.get("provider") == "mock":
        local_path = f"output/{task_id}/final.mp4"
        _write_mock_mp4(local_path)
        url = _public_file_url(local_path)
        result = {"local_path": local_path, "url": url, "metadata": {}}
    else:
        with apply_stage_runtime_config(pixelle_video, request.stage_model_config):
            result = await compose_stage_video(request, task_id)
        local_path = result["local_path"]
        url = result["url"]
    task_manager.update_progress(task_id, 1, 1, "Final video composed")
    return {"assets": [StageAsset(
        frame_id="final",
        asset_type="final_video",
        url=url,
        local_path=local_path,
        metadata={**result.get("metadata", {}), "duration": total_duration, "edit_manifest": request.edit_manifest},
    ).model_dump()]}
```

- [ ] **Step 9: Add routes**

Add these route handlers to `D:\devWorkspace\Pixelle-Video\api\routers\stages.py`:

```python
@router.post("/videos/batch", response_model=StageTaskResponse)
async def video_batch(request: VideoBatchRequest, pixelle_video: PixelleVideoDep):
    if not request.frames:
        raise HTTPException(status_code=400, detail="frames is required")
    task = task_manager.create_task(TaskType.VIDEO_BATCH, request.model_dump(exclude={"stage_model_config"}))
    await task_manager.execute_task(task.task_id, _run_video_batch, request, pixelle_video, task.task_id)
    return StageTaskResponse(ok=True, stage_task_id=task.task_id, assets=[], logs=[])


@router.post("/compose", response_model=StageTaskResponse)
async def compose(request: ComposeRequest, pixelle_video: PixelleVideoDep):
    if not request.segments:
        raise HTTPException(status_code=400, detail="segments is required")
    task = task_manager.create_task(TaskType.COMPOSE, request.model_dump(exclude={"stage_model_config"}))
    await task_manager.execute_task(task.task_id, _run_compose, request, pixelle_video, task.task_id)
    return StageTaskResponse(ok=True, stage_task_id=task.task_id, assets=[], logs=[])
```

- [ ] **Step 10: Run Pixelle stage tests**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_stage_runtime_config.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py tests/test_files_security.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit Pixelle video and compose stage contracts**

```powershell
cd D:\devWorkspace\Pixelle-Video
git add api/schemas/stages.py api/routers/stages.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py
git commit -m "feat: add Pixelle video and compose stage APIs"
```

## Task 3: Add dy_auto State Machine and Idempotent Gates

**Files:**

- Create: `server/app/services/video_production_state.py`
- Modify: `server/app/services/video_production_service.py`
- Create: `server/tests/test_video_production_state_machine.py`

- [ ] **Step 1: Write state machine tests**

Create `server/tests/test_video_production_state_machine.py`:

```python
from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_state import (
    assert_can_start_images,
    assert_can_start_videos,
    assert_can_compose,
    latest_assets_by_frame,
    record_stage_task,
    recompute_run_gate,
)
from app.services.video_production_service import mark_image_stage_assets, run_ai_audit_for_assets


def _run(db, frame_count=2):
    series = Series(title="State", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [
                {"frame_id": f"frame-{index:03d}", "image_prompt": "Prompt", "duration": 5}
                for index in range(1, frame_count + 1)
            ]
        },
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="storyboard_ready",
        current_stage="storyboard_ready",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.commit()
    return run


def _asset(db, run, frame_id, asset_type, version, status, task_id="task-1"):
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url=f"https://cdn.test/{frame_id}-{asset_type}-{version}",
        version=version,
        status=status,
        pixelle_task_id=task_id,
    )
    db.add(asset)
    db.commit()
    return asset


def test_latest_assets_by_frame_uses_highest_version(db):
    run = _run(db, frame_count=1)
    old = _asset(db, run, "frame-001", "image", 1, "approved")
    new = _asset(db, run, "frame-001", "image", 2, "review_pending")

    latest = latest_assets_by_frame(db, run.id, "image")

    assert latest["frame-001"].id == new.id
    assert latest["frame-001"].id != old.id


def test_cannot_start_videos_until_each_latest_image_is_approved(db):
    run = _run(db, frame_count=2)
    run.status = "image_approved"
    _asset(db, run, "frame-001", "image", 1, "approved")
    _asset(db, run, "frame-002", "image", 1, "review_pending")
    db.commit()

    try:
        assert_can_start_videos(db, run)
    except ValueError as exc:
        assert "Images not approved: frame-002" in str(exc)
    else:
        raise AssertionError("Expected gate failure")


def test_start_video_stage_rejects_duplicate_inflight_run(db):
    run = _run(db, frame_count=1)
    run.status = "video_batch_running"
    run.current_stage = "video_rendering"
    record_stage_task(run, "video_rendering", "video-task-1")
    _asset(db, run, "frame-001", "image", 1, "approved")
    db.commit()

    try:
        assert_can_start_videos(db, run)
    except ValueError as exc:
        assert "Video stage already started" in str(exc)
    else:
        raise AssertionError("Expected duplicate video stage gate failure")


def test_start_compose_stage_rejects_duplicate_inflight_run(db):
    run = _run(db, frame_count=1)
    run.status = "composing"
    run.current_stage = "composition"
    record_stage_task(run, "composition", "compose-task-1")
    _asset(db, run, "frame-001", "video_segment", 1, "approved")
    db.commit()

    try:
        assert_can_compose(db, run)
    except ValueError as exc:
        assert "Compose stage already started" in str(exc)
    else:
        raise AssertionError("Expected duplicate compose stage gate failure")


def test_sync_image_stage_results_is_idempotent_for_same_pixelle_task(db):
    run = _run(db, frame_count=1)
    assets = [{"frame_id": "frame-001", "url": "https://cdn.test/image.png", "metadata": {}}]

    first = mark_image_stage_assets(db, run, assets, pixelle_task_id="image-task-1")
    first[0].status = "approved"
    db.commit()
    second = mark_image_stage_assets(db, run, assets, pixelle_task_id="image-task-1")

    assert second[0].id == first[0].id
    assert db.query(VideoProductionAsset).filter_by(run_id=run.id, asset_type="image").count() == 1


def test_ai_audit_is_idempotent_for_existing_asset_review(db):
    run = _run(db, frame_count=1)
    asset = _asset(db, run, "frame-001", "image", 1, "review_pending")
    db.add(VideoReviewRecord(asset_id=asset.id, run_id=run.id, review_type="ai", status="approved", score=1.0))
    db.commit()

    run_ai_audit_for_assets(db, run, [asset])

    assert db.query(VideoReviewRecord).filter_by(asset_id=asset.id, review_type="ai").count() == 1


def test_recompute_image_gate_sets_image_approved_when_all_latest_images_pass(db):
    run = _run(db, frame_count=2)
    _asset(db, run, "frame-001", "image", 1, "approved")
    _asset(db, run, "frame-002", "image", 1, "approved")

    recompute_run_gate(db, run.id, "image")
    db.refresh(run)

    assert run.status == "image_approved"
    assert run.current_stage == "image_review"


def test_recompute_video_gate_sets_video_segments_approved_when_all_latest_segments_pass(db):
    run = _run(db, frame_count=2)
    _asset(db, run, "frame-001", "video_segment", 1, "approved")
    _asset(db, run, "frame-002", "video_segment", 1, "approved")

    recompute_run_gate(db, run.id, "video_segment")
    db.refresh(run)

    assert run.status == "video_segments_approved"
    assert run.current_stage == "video_review"


def test_cannot_compose_until_latest_video_segments_are_approved(db):
    run = _run(db, frame_count=1)
    run.status = "video_segments_approved"
    _asset(db, run, "frame-001", "video_segment", 1, "approved")
    _asset(db, run, "frame-001", "video_segment", 2, "review_pending")
    db.commit()

    try:
        assert_can_compose(db, run)
    except ValueError as exc:
        assert "Video segments not approved: frame-001" in str(exc)
    else:
        raise AssertionError("Expected compose gate failure")


def test_start_images_is_allowed_only_from_storyboard_ready(db):
    run = _run(db)
    assert_can_start_images(run)
    run.status = "image_batch_running"

    try:
        assert_can_start_images(run)
    except ValueError as exc:
        assert "Image stage already started" in str(exc)
    else:
        raise AssertionError("Expected start image gate failure")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_state_machine.py -q
```

Expected: FAIL because `video_production_state.py` does not exist.

- [ ] **Step 3: Create state machine service**

Create `server/app/services/video_production_state.py`:

```python
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import VideoProductionAsset, VideoProductionRun


IMAGE_READY_STATUS = "image_approved"
VIDEO_READY_STATUS = "video_segments_approved"


def storyboard_frame_ids(run: VideoProductionRun) -> list[str]:
    frames = (run.storyboard_json or {}).get("frames") or []
    return [str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}") for index, frame in enumerate(frames)]


def latest_assets_by_frame(db: Session, run_id: str, asset_type: str) -> dict[str, VideoProductionAsset]:
    rows = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run_id,
        VideoProductionAsset.asset_type == asset_type,
    ).order_by(VideoProductionAsset.frame_id.asc(), VideoProductionAsset.version.desc()).all()
    latest: dict[str, VideoProductionAsset] = {}
    for row in rows:
        latest.setdefault(row.frame_id, row)
    return latest


def missing_or_unapproved_frames(db: Session, run: VideoProductionRun, asset_type: str) -> list[str]:
    latest = latest_assets_by_frame(db, run.id, asset_type)
    missing: list[str] = []
    for frame_id in storyboard_frame_ids(run):
        asset = latest.get(frame_id)
        if not asset or asset.status != "approved":
            missing.append(frame_id)
    return missing


def assert_can_start_images(run: VideoProductionRun) -> None:
    if run.status not in {"draft", "storyboard_ready"}:
        raise ValueError("Image stage already started")
    if run.pixelle_stage_task_id:
        raise ValueError("Image stage already has a Pixelle task")


def assert_can_start_videos(db: Session, run: VideoProductionRun) -> None:
    if run.status == "video_batch_running":
        raise ValueError("Video stage already started")
    if run.status != IMAGE_READY_STATUS:
        raise ValueError("Video stage can start only after images are approved")
    missing = missing_or_unapproved_frames(db, run, "image")
    if missing:
        raise ValueError(f"Images not approved: {', '.join(missing)}")


def assert_can_compose(db: Session, run: VideoProductionRun) -> None:
    if run.status == "composing":
        raise ValueError("Compose stage already started")
    if run.status != VIDEO_READY_STATUS:
        raise ValueError("Compose can start only after video segments are approved")
    missing = missing_or_unapproved_frames(db, run, "video_segment")
    if missing:
        raise ValueError(f"Video segments not approved: {', '.join(missing)}")


def record_stage_task(run: VideoProductionRun, stage: str, task_id: str, status: str = "submitted") -> None:
    trace = dict(run.model_trace_json or {})
    stage_tasks = dict(trace.get("stage_tasks") or {})
    stage_tasks[stage] = {
        "task_id": task_id,
        "status": status,
        "updated_at": bj_now().isoformat(),
    }
    trace["stage_tasks"] = stage_tasks
    run.model_trace_json = trace


def recompute_run_gate(db: Session, run_id: str, asset_type: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise ValueError("Run not found")
    missing = missing_or_unapproved_frames(db, run, asset_type)
    latest = latest_assets_by_frame(db, run.id, asset_type)
    latest_statuses = [latest[frame_id].status for frame_id in latest if latest.get(frame_id)]

    if asset_type == "image":
        run.current_stage = "image_review"
        if not missing:
            run.status = "image_approved"
        elif any(status == "rejected" for status in latest_statuses):
            run.status = "image_human_review_required"
        else:
            run.status = "image_review_pending"
    elif asset_type == "video_segment":
        run.current_stage = "video_review"
        if not missing:
            run.status = "video_segments_approved"
        elif any(status == "rejected" for status in latest_statuses):
            run.status = "video_human_review_required"
        else:
            run.status = "video_review_pending"
    else:
        raise ValueError(f"Unsupported gate asset type: {asset_type}")

    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run
```

- [ ] **Step 4: Wire existing service to state functions**

Modify `server/app/services/video_production_service.py`:

```python
from app.services.video_production_state import (
    assert_can_start_images,
    assert_can_start_videos,
    assert_can_compose,
    latest_assets_by_frame,
    record_stage_task,
    recompute_run_gate,
)
```

Then replace the local `latest_assets_by_frame` function with the imported one. In `start_image_stage`, add:

```python
    assert_can_start_images(run)
```

before building frames.

In `mark_image_stage_submitted`, call:

```python
    record_stage_task(run, "image_generation", stage_task_id)
```

before `db.commit()` so each stage task is preserved in `model_trace_json["stage_tasks"]` instead of relying on the single overwritten `pixelle_stage_task_id`.

At the top of `mark_image_stage_assets`, add the same idempotency guard used by the video stage:

```python
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "image",
        VideoProductionAsset.pixelle_task_id == pixelle_task_id,
    ).all()
    if existing:
        return existing
```

In `run_ai_audit_for_assets`, skip assets that already have an AI review record so repeated sync calls do not create duplicate reviews:

```python
        existing_review = db.query(VideoReviewRecord).filter(
            VideoReviewRecord.asset_id == asset.id,
            VideoReviewRecord.review_type == "ai",
        ).first()
        if existing_review:
            continue
```

In `run_ai_audit_for_assets`, after refreshing assets, add:

```python
    if assets:
        recompute_run_gate(db, run.id, assets[0].asset_type)
```

In `approve_asset` and `reject_asset`, after the asset commit/refresh, add:

```python
    recompute_run_gate(db, asset.run_id, asset.asset_type)
```

- [ ] **Step 5: Run state machine tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_state_machine.py tests/test_video_production_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit state machine**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/video_production_state.py server/app/services/video_production_service.py server/tests/test_video_production_state_machine.py server/tests/test_video_production_service.py
git commit -m "feat: add video production state gates"
```

## Task 4: Add dy_auto Pixelle Video and Compose Client

**Files:**

- Modify: `server/app/services/pixelle_stage_client.py`
- Modify: `server/tests/test_pixelle_stage_client.py`

- [ ] **Step 1: Add client tests**

Append to `server/tests/test_pixelle_stage_client.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_submit_video_batch_calls_pixelle_stage_api(monkeypatch):
    from app.services import pixelle_stage_client

    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "video-task-1"}

    monkeypatch.setattr(pixelle_stage_client, "_pixelle_request", fake_request)

    response = await pixelle_stage_client.submit_video_batch(
        db=None,
        run_id="run-1",
        frames=[{"frame_id": "frame-001", "approved_image_url": "image.png", "duration": 5}],
        model_config={"provider": "mock"},
    )

    assert response["stage_task_id"] == "video-task-1"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/stages/videos/batch"
    assert calls[0][2]["external_run_id"] == "run-1"
    assert calls[0][2]["frames"][0]["approved_image_url"] == "image.png"


@pytest.mark.asyncio
async def test_submit_compose_calls_pixelle_stage_api(monkeypatch):
    from app.services import pixelle_stage_client

    calls = []

    async def fake_request(method, path, db=None, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return {"ok": True, "stage_task_id": "compose-task-1"}

    monkeypatch.setattr(pixelle_stage_client, "_pixelle_request", fake_request)

    response = await pixelle_stage_client.submit_compose(
        db=None,
        run_id="run-1",
        segments=[{"frame_id": "frame-001", "video_url": "segment.mp4", "duration": 5}],
        edit_manifest={"output_spec": {"resolution": "1080x1920"}},
        model_config={"provider": "mock"},
    )

    assert response["stage_task_id"] == "compose-task-1"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/stages/compose"
    assert calls[0][2]["segments"][0]["video_url"] == "segment.mp4"
```

- [ ] **Step 2: Run client tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_stage_client.py -q
```

Expected: FAIL because `submit_video_batch` and `submit_compose` are missing.

- [ ] **Step 3: Add client functions**

Append to `server/app/services/pixelle_stage_client.py`:

```python
async def submit_video_batch(
    db: Session | None,
    run_id: str,
    frames: list[dict],
    model_config: dict,
    template_config: dict | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "frames": frames,
        "model_config": model_config,
        "template_config": template_config or {},
    }
    return await _pixelle_request("POST", "/api/stages/videos/batch", db, json=payload)


async def submit_compose(
    db: Session | None,
    run_id: str,
    segments: list[dict],
    edit_manifest: dict,
    model_config: dict | None = None,
) -> dict:
    payload = {
        "external_run_id": run_id,
        "segments": segments,
        "edit_manifest": edit_manifest,
        "model_config": model_config or {"provider": "mock", "model": "compose"},
    }
    return await _pixelle_request("POST", "/api/stages/compose", db, json=payload)
```

- [ ] **Step 4: Run client tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_pixelle_stage_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit client additions**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/pixelle_stage_client.py server/tests/test_pixelle_stage_client.py
git commit -m "feat: add Pixelle video and compose clients"
```

## Task 5: Add dy_auto Video Segment Stage

**Files:**

- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_video_production_video_stage.py`
- Modify: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Write video stage service tests**

Create `server/tests/test_video_production_video_stage.py`:

```python
import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_service import start_video_stage, sync_video_stage_results


def _run_with_approved_images(db):
    series = Series(title="Video Stage", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={
            "frames": [
                {
                    "frame_id": "frame-001",
                    "image_prompt": "Image prompt",
                    "video_prompt": "Video prompt",
                    "narration": "Narration",
                    "duration": 5,
                    "audio_mode": "tts",
                    "reference_urls": ["https://cdn.test/ref.png"],
                }
            ]
        },
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="image_approved",
        current_stage="image_review",
        storyboard_json=episode.storyboard_json,
    )
    db.add(run)
    db.flush()
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="image",
        stage="image_generation",
        url="https://cdn.test/image.png",
        version=1,
        status="approved",
    ))
    db.commit()
    return run


@pytest.mark.asyncio
async def test_start_video_stage_submits_approved_images(db, monkeypatch):
    run = _run_with_approved_images(db)
    calls = []

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        calls.append({"run_id": run_id, "frames": frames, "model_config": model_config})
        return {"ok": True, "stage_task_id": "video-task-1"}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)

    updated = await start_video_stage(db, run.id)

    assert updated.status == "video_batch_running"
    assert updated.current_stage == "video_rendering"
    assert updated.pixelle_stage_task_id == "video-task-1"
    assert calls[0]["frames"][0]["approved_image_url"] == "https://cdn.test/image.png"
    assert calls[0]["frames"][0]["video_prompt"] == "Video prompt"


@pytest.mark.asyncio
async def test_sync_video_stage_saves_segments_and_ai_review(db, monkeypatch):
    run = _run_with_approved_images(db)
    run.pixelle_stage_task_id = "video-task-1"
    run.status = "video_batch_running"
    db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [
                {
                    "frame_id": "frame-001",
                    "asset_type": "video_segment",
                    "url": "https://cdn.test/segment.mp4",
                    "local_path": "output/segment.mp4",
                    "metadata": {"duration": 5},
                }
            ],
        }

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"})
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.95, "pass_fail": True, "issues": []})

    assets = await sync_video_stage_results(db, run.id)

    assert assets[0].asset_type == "video_segment"
    assert assets[0].status == "approved"
    assert db.query(VideoReviewRecord).filter_by(asset_id=assets[0].id, review_type="ai").count() == 1
    db.refresh(run)
    assert run.status == "video_segments_approved"
```

- [ ] **Step 2: Run video stage tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_video_stage.py -q
```

Expected: FAIL because `start_video_stage` and `sync_video_stage_results` are missing.

- [ ] **Step 3: Add video stage helpers**

Add to `server/app/services/video_production_service.py`:

```python
from app.services.pixelle_stage_client import get_stage_task, submit_compose, submit_image_batch, submit_video_batch
```

Then add:

```python
def video_stage_frames(db: Session, run: VideoProductionRun) -> list[dict]:
    latest_images = latest_assets_by_frame(db, run.id, "image")
    frames = (run.storyboard_json or {}).get("frames") or []
    payload = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        image = latest_images.get(frame_id)
        if not image or image.status != "approved":
            raise VideoProductionError(f"Approved image missing for frame {frame_id}")
        payload.append({
            "frame_id": frame_id,
            "approved_image_url": image.url,
            "video_prompt": frame.get("video_prompt") or frame.get("image_prompt", ""),
            "reference_urls": frame.get("reference_urls") or [],
            "duration": float(frame.get("duration") or 5),
            "audio_mode": frame.get("audio_mode") or "tts",
        })
    return payload


def video_stage_frame_for_asset(db: Session, run: VideoProductionRun, frame_id: str) -> dict:
    for frame in video_stage_frames(db, run):
        if frame["frame_id"] == frame_id:
            return frame
    raise VideoProductionError(f"Frame not found for video regeneration: {frame_id}")
```

- [ ] **Step 4: Add start video stage**

Add to `server/app/services/video_production_service.py`:

```python
async def start_video_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    assert_can_start_videos(db, run)
    frames = video_stage_frames(db, run)
    model_config = resolve_runtime_model_config(db, "video_rendering")
    response = await submit_video_batch(
        db=db,
        run_id=run.id,
        frames=frames,
        model_config=model_config,
    )
    run.status = "video_batch_running"
    run.current_stage = "video_rendering"
    run.pixelle_stage_task_id = response["stage_task_id"]
    record_stage_task(run, "video_rendering", response["stage_task_id"])
    trace = run.model_trace_json or {}
    trace["video_rendering"] = redact_runtime_model_config(model_config)
    run.model_trace_json = trace
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run
```

- [ ] **Step 5: Add video sync stage**

Add to `server/app/services/video_production_service.py`:

```python
def mark_video_stage_assets(db: Session, run: VideoProductionRun, assets: list[dict], pixelle_task_id: str) -> list[VideoProductionAsset]:
    saved = []
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "video_segment",
        VideoProductionAsset.pixelle_task_id == pixelle_task_id,
    ).all()
    if existing:
        return existing
    for item in assets:
        frame_id = item["frame_id"]
        asset = VideoProductionAsset(
            run_id=run.id,
            episode_id=run.episode_id,
            frame_id=frame_id,
            asset_type="video_segment",
            stage="video_rendering",
            url=item.get("url", ""),
            local_path=item.get("local_path", ""),
            thumbnail_url=item.get("thumbnail_url", ""),
            duration_seconds=(item.get("metadata") or {}).get("duration"),
            version=_next_asset_version(db, run.id, frame_id, "video_segment"),
            metadata_json={
                **(item.get("metadata") or {}),
                "error_code": item.get("error_code"),
                "message": item.get("message"),
                "retryable": item.get("retryable", True),
            },
            status="failed" if item.get("status") == "failed" else "review_pending",
            pixelle_task_id=pixelle_task_id,
        )
        db.add(asset)
        saved.append(asset)
    run.status = "video_review_pending"
    run.current_stage = "video_review"
    run.updated_at = bj_now()
    db.commit()
    for asset in saved:
        db.refresh(asset)
    return saved


async def sync_video_stage_results(db: Session, run_id: str) -> list[VideoProductionAsset]:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Video stage is not complete: {status.get('status')}")
    assets = mark_video_stage_assets(db, run, status.get("assets", []), pixelle_task_id=run.pixelle_stage_task_id)
    run_ai_audit_for_assets(db, run, assets)
    return assets
```

- [ ] **Step 6: Add routes**

Modify imports in `server/app/routers/video_production.py`:

```python
from app.services.video_production_service import (
    VideoProductionError,
    approve_asset,
    create_regenerated_image_asset,
    create_run_from_episode,
    reject_asset,
    start_image_stage,
    start_video_stage,
    sync_image_stage_results,
    sync_video_stage_results,
)
```

Add route handlers:

```python
@router.post("/runs/{run_id}/start-videos")
async def start_videos(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = await start_video_stage(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.post("/runs/{run_id}/sync-video-results")
async def sync_videos(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        assets = await sync_video_stage_results(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "assets": [_asset_payload(asset) for asset in assets]}
```

- [ ] **Step 7: Run video stage tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_video_stage.py tests/test_video_production_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit video stage**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_video_production_video_stage.py server/tests/test_video_production_api.py
git commit -m "feat: add dy_auto video segment stage"
```

## Task 6: Add dy_auto Compose Stage and Video Library Writeback

**Files:**

- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_video_production_compose.py`

- [ ] **Step 1: Write compose tests**

Create `server/tests/test_video_production_compose.py`:

```python
import pytest

from app.db_models import Episode, GeneratedVideo, Series, VideoProductionAsset, VideoProductionRun
from app.services.video_production_service import approve_asset, reject_asset, start_compose_stage, sync_compose_stage_results


def _run_with_segments(db):
    series = Series(title="Compose", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "narration": "hello", "duration": 5}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(
        series_id=series.id,
        episode_id=episode.id,
        status="video_segments_approved",
        current_stage="video_review",
        storyboard_json=episode.storyboard_json,
        edit_manifest_json={"output_spec": {"aspect_ratio": "9:16", "resolution": "1080x1920"}},
    )
    db.add(run)
    db.flush()
    db.add(VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="frame-001",
        asset_type="video_segment",
        stage="video_rendering",
        url="https://cdn.test/segment.mp4",
        duration_seconds=5,
        version=1,
        status="approved",
    ))
    db.commit()
    return run, episode


@pytest.mark.asyncio
async def test_start_compose_stage_submits_approved_segments(db, monkeypatch):
    run, _episode = _run_with_segments(db)
    calls = []

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        calls.append({"run_id": run_id, "segments": segments, "edit_manifest": edit_manifest})
        return {"ok": True, "stage_task_id": "compose-task-1"}

    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)

    updated = await start_compose_stage(db, run.id)

    assert updated.status == "composing"
    assert updated.current_stage == "composition"
    assert updated.pixelle_stage_task_id == "compose-task-1"
    assert calls[0]["segments"][0]["video_url"] == "https://cdn.test/segment.mp4"


@pytest.mark.asyncio
async def test_sync_compose_results_writes_episode_and_generated_video(db, monkeypatch):
    run, episode = _run_with_segments(db)
    run.pixelle_stage_task_id = "compose-task-1"
    run.status = "composing"
    db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [
                {
                    "frame_id": "final",
                    "asset_type": "final_video",
                    "url": "https://cdn.test/final.mp4",
                    "local_path": "output/final.mp4",
                    "metadata": {"duration": 5},
                }
            ],
        }

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"})
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.96, "pass_fail": True, "issues": []})

    asset = await sync_compose_stage_results(db, run.id)

    assert asset.asset_type == "final_video"
    assert asset.status == "approved"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "completed"
    assert episode.status == "done"
    assert episode.video_url == "https://cdn.test/final.mp4"
    assert episode.duration_seconds == 5
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 1


@pytest.mark.asyncio
async def test_sync_compose_results_enters_final_review_when_audit_fails(db, monkeypatch):
    run, episode = _run_with_segments(db)
    run.pixelle_stage_task_id = "compose-task-1"
    run.status = "composing"
    db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [{
                "frame_id": "final",
                "asset_type": "final_video",
                "url": "https://cdn.test/final.mp4",
                "local_path": "output/final.mp4",
                "metadata": {"duration": 5},
            }],
        }

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "model_name": "audit"})
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.4, "pass_fail": False, "issues": ["bad cut"]})

    asset = await sync_compose_stage_results(db, run.id)

    assert asset.asset_type == "final_video"
    assert asset.status == "review_pending"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "final_review_pending"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0


def test_human_approve_final_video_completes_run_after_final_audit_failure(db):
    run, episode = _run_with_segments(db)
    final_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url="https://cdn.test/final.mp4",
        local_path="output/final.mp4",
        duration_seconds=5,
        version=1,
        status="review_pending",
        pixelle_task_id="compose-task-1",
    )
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    db.add(final_asset)
    db.commit()

    approved = approve_asset(db, final_asset.id, reviewer_user_id="test-user", comment="approved")

    assert approved.status == "approved"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "completed"
    assert episode.status == "done"
    assert episode.video_url == "https://cdn.test/final.mp4"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 1


def test_human_reject_final_video_returns_run_to_compose_ready(db):
    run, episode = _run_with_segments(db)
    final_asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url="https://cdn.test/final.mp4",
        local_path="output/final.mp4",
        duration_seconds=5,
        version=1,
        status="review_pending",
        pixelle_task_id="compose-task-1",
    )
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    db.add(final_asset)
    db.commit()

    rejected = reject_asset(db, final_asset.id, reviewer_user_id="test-user", comment="bad cut")

    assert rejected.status == "rejected"
    db.refresh(run)
    db.refresh(episode)
    assert run.status == "video_segments_approved"
    assert run.current_stage == "video_review"
    assert episode.video_url is None
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run.id).count() == 0
```

- [ ] **Step 2: Run compose tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_compose.py -q
```

Expected: FAIL because compose service functions are missing.

- [ ] **Step 3: Add segment payload helper**

Add to `server/app/services/video_production_service.py`:

```python
def compose_segments(db: Session, run: VideoProductionRun) -> list[dict]:
    latest_segments = latest_assets_by_frame(db, run.id, "video_segment")
    frames = (run.storyboard_json or {}).get("frames") or []
    segments = []
    for index, frame in enumerate(frames):
        frame_id = _frame_id(frame, index)
        segment = latest_segments.get(frame_id)
        if not segment or segment.status != "approved":
            raise VideoProductionError(f"Approved video segment missing for frame {frame_id}")
        segments.append({
            "frame_id": frame_id,
            "video_url": segment.url,
            "duration": float(segment.duration_seconds or frame.get("duration") or 5),
            "narration": frame.get("narration", ""),
        })
    return segments
```

- [ ] **Step 4: Add default edit manifest**

Add to `server/app/services/video_production_service.py`:

```python
def default_edit_manifest(run: VideoProductionRun) -> dict:
    existing = run.edit_manifest_json or {}
    if existing:
        return existing
    return {
        "subtitle_style": {"position": "bottom", "font_size": 42},
        "bgm_policy": {"mode": "auto", "volume": 0.18},
        "intro_outro": {"intro_enabled": False, "outro_enabled": False},
        "watermark": {"enabled": False},
        "output_spec": {"aspect_ratio": "9:16", "resolution": "1080x1920"},
    }
```

- [ ] **Step 5: Add compose start**

Add to `server/app/services/video_production_service.py`:

```python
async def start_compose_stage(db: Session, run_id: str) -> VideoProductionRun:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    assert_can_compose(db, run)
    segments = compose_segments(db, run)
    edit_manifest = default_edit_manifest(run)
    response = await submit_compose(
        db=db,
        run_id=run.id,
        segments=segments,
        edit_manifest=edit_manifest,
        model_config={"provider": "mock", "model": "compose"},
    )
    run.status = "composing"
    run.current_stage = "composition"
    run.pixelle_stage_task_id = response["stage_task_id"]
    record_stage_task(run, "composition", response["stage_task_id"])
    run.edit_manifest_json = edit_manifest
    run.updated_at = bj_now()
    db.commit()
    db.refresh(run)
    return run
```

- [ ] **Step 6: Add final writeback**

Add to `server/app/services/video_production_service.py`:

```python
def complete_final_video(db: Session, run: VideoProductionRun, asset: VideoProductionAsset) -> VideoProductionAsset:
    from app.db_models import GeneratedVideo, Series

    duration = int(asset.duration_seconds or 0)
    episode = db.query(Episode).filter(Episode.id == run.episode_id).first()
    series = db.query(Series).filter(Series.id == run.series_id).first()
    title = (episode.title if episode and episode.title else series.title if series else "Generated video")
    keyword = title or run.id
    if episode:
        episode.video_url = asset.url
        episode.duration_seconds = duration or episode.duration_seconds
        episode.status = "done"

    video = db.query(GeneratedVideo).filter(GeneratedVideo.pixelle_task_id == run.id).first()
    if not video:
        video = GeneratedVideo(
            keyword=keyword,
            title=title,
            video_path=asset.local_path or asset.url,
            duration=duration,
            status="completed",
            pixelle_task_id=run.id,
        )
        db.add(video)
    else:
        video.video_path = asset.local_path or asset.url
        video.duration = duration
        video.status = "completed"

    run.status = "completed"
    run.current_stage = "completed"
    run.completed_at = bj_now()
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def approve_final_video_asset(db: Session, asset: VideoProductionAsset, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer final video version exists. Reload before reviewing.")
    asset.status = "approved"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="approved",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    db.flush()
    return complete_final_video(db, run, asset)


def reject_final_video_asset(db: Session, asset: VideoProductionAsset, reviewer_user_id: str | None, comment: str = "") -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    latest = latest_assets_by_frame(db, asset.run_id, "final_video").get(asset.frame_id)
    if latest and latest.id != asset.id:
        raise VideoProductionError("A newer final video version exists. Reload before reviewing.")
    asset.status = "rejected"
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=asset.run_id,
        review_type="human",
        status="rejected",
        reviewer_user_id=reviewer_user_id,
        comment=comment,
    ))
    run.status = "video_segments_approved"
    run.current_stage = "video_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def run_final_audit_for_asset(db: Session, run: VideoProductionRun, asset: VideoProductionAsset) -> VideoProductionAsset:
    try:
        audit_model = resolve_runtime_model_config(db, "quality_audit")
    except Exception:
        audit_model = {}

    if not audit_model or not audit_model.get("api_key"):
        result = {"score": 0.0, "pass_fail": False, "issues": ["Final audit model not configured"]}
    else:
        try:
            from app.routers.audit import _do_audit
            result = _do_audit(audit_model, asset.url, None)
        except Exception as exc:
            result = {"score": 0.0, "pass_fail": False, "issues": [str(exc)]}

    gate = classify_audit_gate(result, error=False)
    db.add(VideoReviewRecord(
        asset_id=asset.id,
        run_id=run.id,
        review_type="ai",
        status=gate["gate_status"],
        score=gate["score"],
        issues_json=gate.get("issues", []),
        model_trace_json={"auditor_model": audit_model.get("provider", "unknown"), "auditor_model_name": audit_model.get("model_name", "")},
    ))
    if gate["gate_status"] == "approved":
        asset.status = "approved"
        db.commit()
        return complete_final_video(db, run, asset)

    asset.status = "review_pending"
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return asset


def persist_final_video(db: Session, run: VideoProductionRun, item: dict) -> VideoProductionAsset:
    metadata = item.get("metadata") or {}
    duration = int(metadata.get("duration") or 0)
    existing = db.query(VideoProductionAsset).filter(
        VideoProductionAsset.run_id == run.id,
        VideoProductionAsset.asset_type == "final_video",
        VideoProductionAsset.pixelle_task_id == run.pixelle_stage_task_id,
    ).first()
    if existing:
        return existing
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=run.episode_id,
        frame_id="final",
        asset_type="final_video",
        stage="composition",
        url=item.get("url", ""),
        local_path=item.get("local_path", ""),
        thumbnail_url=item.get("thumbnail_url", ""),
        duration_seconds=duration,
        version=_next_asset_version(db, run.id, "final", "final_video"),
        metadata_json=metadata,
        status="review_pending",
        pixelle_task_id=run.pixelle_stage_task_id,
    )
    db.add(asset)
    run.status = "final_review_pending"
    run.current_stage = "final_review"
    run.updated_at = bj_now()
    db.commit()
    db.refresh(asset)
    return run_final_audit_for_asset(db, run, asset)
```

Then update `approve_asset` near the top of the same service so final videos complete the run instead of going through `recompute_run_gate`. The branch should be immediately after loading `asset` and checking that it exists:

```python
    if asset.asset_type == "final_video":
        return approve_final_video_asset(db, asset, reviewer_user_id, comment)
```

Then update `reject_asset` with the matching final-video branch so human rejection returns the run to the compose-ready state instead of calling `recompute_run_gate` with an unsupported asset type:

```python
    if asset.asset_type == "final_video":
        return reject_final_video_asset(db, asset, reviewer_user_id, comment)
```

- [ ] **Step 7: Add compose sync**

Add to `server/app/services/video_production_service.py`:

```python
async def sync_compose_stage_results(db: Session, run_id: str) -> VideoProductionAsset:
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    if not run.pixelle_stage_task_id:
        raise VideoProductionError("Run has no Pixelle stage task")
    status = await get_stage_task(db, run.pixelle_stage_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Compose stage is not complete: {status.get('status')}")
    final_assets = [item for item in status.get("assets", []) if item.get("asset_type") == "final_video"]
    if not final_assets:
        raise VideoProductionError("Compose stage returned no final video")
    return persist_final_video(db, run, final_assets[0])
```

- [ ] **Step 8: Add compose routes**

Add imports and routes to `server/app/routers/video_production.py`:

```python
@router.post("/runs/{run_id}/compose")
async def compose_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        run = await start_compose_stage(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "run": _run_payload(run)}


@router.post("/runs/{run_id}/sync-compose-results")
async def sync_compose(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = await sync_compose_stage_results(db, run_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
```

- [ ] **Step 9: Run compose tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_compose.py tests/test_video_production_api.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit compose stage**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_video_production_compose.py server/tests/test_video_production_api.py
git commit -m "feat: add final compose and video library writeback"
```

## Task 7: Add Real Single-Item Regeneration Flow

**Files:**

- Modify: `server/app/services/video_production_service.py`
- Modify: `server/app/routers/video_production.py`
- Create: `server/tests/test_video_production_regeneration.py`

- [ ] **Step 1: Write regeneration tests**

Create `server/tests/test_video_production_regeneration.py`:

```python
import pytest

from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord
from app.services.video_production_service import start_asset_regeneration, sync_regenerated_asset


def _asset_run(db, asset_type="image", frame_id="frame-001"):
    series = Series(title="Regen", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={
            "frames": [
                {"frame_id": "frame-001", "image_prompt": "new image 1", "video_prompt": "new video 1", "duration": 5},
                {"frame_id": "frame-002", "image_prompt": "new image 2", "video_prompt": "new video 2", "duration": 6},
            ]
        },
    )
    db.add(episode)
    db.flush()
    run_status = "image_human_review_required" if asset_type == "image" else "video_human_review_required"
    run_stage = "image_review" if asset_type == "image" else "video_review"
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, status=run_status, current_stage=run_stage, storyboard_json=episode.storyboard_json)
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(
        run_id=run.id,
        episode_id=episode.id,
        frame_id=frame_id,
        asset_type=asset_type,
        stage="image_generation" if asset_type == "image" else "video_rendering",
        url="https://cdn.test/old.png",
        version=1,
        status="rejected",
    )
    db.add(asset)
    if asset_type == "video_segment":
        for image_frame_id in ("frame-001", "frame-002"):
            db.add(VideoProductionAsset(
                run_id=run.id,
                episode_id=episode.id,
                frame_id=image_frame_id,
                asset_type="image",
                stage="image_generation",
                url=f"https://cdn.test/{image_frame_id}.png",
                version=1,
                status="approved",
            ))
    db.commit()
    return run, asset


@pytest.mark.asyncio
async def test_start_video_segment_regeneration_uses_selected_frame(db, monkeypatch):
    _run, asset = _asset_run(db, "video_segment", frame_id="frame-002")
    calls = []

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        calls.append(frames)
        return {"ok": True, "stage_task_id": "regen-video-task"}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)

    updated = await start_asset_regeneration(db, asset.id)

    assert updated.status == "regenerating"
    assert updated.pixelle_task_id == "regen-video-task"
    assert calls[0][0]["frame_id"] == "frame-002"
    assert calls[0][0]["duration"] == 6


@pytest.mark.asyncio
async def test_start_image_regeneration_marks_old_asset_regenerating(db, monkeypatch):
    _run, asset = _asset_run(db, "image")

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        return {"ok": True, "stage_task_id": "regen-image-task"}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)

    updated = await start_asset_regeneration(db, asset.id)

    assert updated.status == "regenerating"
    assert updated.pixelle_task_id == "regen-image-task"


@pytest.mark.asyncio
async def test_sync_regenerated_asset_creates_next_version(db, monkeypatch):
    _run, asset = _asset_run(db, "image")
    asset.status = "regenerating"
    asset.pixelle_task_id = "regen-image-task"
    db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [{"frame_id": "frame-001", "asset_type": "image", "url": "https://cdn.test/new.png", "metadata": {}}],
        }

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {})

    new_asset = await sync_regenerated_asset(db, asset.id)

    assert new_asset.version == 2
    assert new_asset.status == "review_pending"
    assert new_asset.url == "https://cdn.test/new.png"
    assert db.query(VideoReviewRecord).filter_by(asset_id=new_asset.id, review_type="ai").count() == 1


@pytest.mark.asyncio
async def test_sync_regenerated_video_segment_creates_ai_review(db, monkeypatch):
    _run, asset = _asset_run(db, "video_segment", frame_id="frame-002")
    asset.status = "regenerating"
    asset.pixelle_task_id = "regen-video-task"
    db.commit()

    async def fake_get_stage_task(db, stage_task_id):
        return {
            "ok": True,
            "status": "completed",
            "assets": [{"frame_id": "frame-002", "asset_type": "video_segment", "url": "https://cdn.test/new.mp4", "metadata": {"duration": 6}}],
        }

    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {})

    new_asset = await sync_regenerated_asset(db, asset.id)

    assert new_asset.asset_type == "video_segment"
    assert new_asset.version == 2
    assert db.query(VideoReviewRecord).filter_by(asset_id=new_asset.id, review_type="ai").count() == 1
```

- [ ] **Step 2: Run regeneration tests to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_regeneration.py -q
```

Expected: FAIL because `start_asset_regeneration` and `sync_regenerated_asset` are missing.

- [ ] **Step 3: Add regeneration start**

Add to `server/app/services/video_production_service.py`:

```python
async def start_asset_regeneration(db: Session, asset_id: str) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not asset:
        raise VideoProductionError("Asset not found")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == asset.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    frames = (run.storyboard_json or {}).get("frames") or []
    frame = next((item for index, item in enumerate(frames) if _frame_id(item, index) == asset.frame_id), None)
    if not frame:
        raise VideoProductionError("Frame not found in storyboard")

    if asset.asset_type == "image":
        model_config = resolve_runtime_model_config(db, "image_generation")
        response = await submit_image_batch(
            db=db,
            run_id=run.id,
            episode_id=run.episode_id,
            frames=[{
                "frame_id": asset.frame_id,
                "image_prompt": frame.get("image_prompt", ""),
                "reference_urls": frame.get("reference_urls") or [],
                "style_constraints": {
                    "character_ids": frame.get("character_ids") or [],
                    "scene_id": frame.get("scene_id"),
                    "continuity_notes": frame.get("continuity_notes", ""),
                },
                "duration": float(frame.get("duration") or 5),
            }],
            model_config=model_config,
        )
    elif asset.asset_type == "video_segment":
        model_config = resolve_runtime_model_config(db, "video_rendering")
        response = await submit_video_batch(
            db=db,
            run_id=run.id,
            frames=[video_stage_frame_for_asset(db, run, asset.frame_id)],
            model_config=model_config,
        )
    else:
        raise VideoProductionError(f"Unsupported regeneration asset type: {asset.asset_type}")

    asset.status = "regenerating"
    asset.pixelle_task_id = response["stage_task_id"]
    record_stage_task(run, f"regeneration:{asset.asset_type}:{asset.frame_id}", response["stage_task_id"])
    db.commit()
    db.refresh(asset)
    return asset
```

- [ ] **Step 4: Add regeneration sync**

Add to `server/app/services/video_production_service.py`:

```python
async def sync_regenerated_asset(db: Session, asset_id: str) -> VideoProductionAsset:
    old = db.query(VideoProductionAsset).filter(VideoProductionAsset.id == asset_id).first()
    if not old:
        raise VideoProductionError("Asset not found")
    if not old.pixelle_task_id:
        raise VideoProductionError("Asset has no regeneration task")
    run = db.query(VideoProductionRun).filter(VideoProductionRun.id == old.run_id).first()
    if not run:
        raise VideoProductionError("Run not found")
    status = await get_stage_task(db, old.pixelle_task_id)
    if status.get("status") not in ("completed", "succeeded", "done"):
        raise VideoProductionError(f"Regeneration task is not complete: {status.get('status')}")
    generated = next((item for item in status.get("assets", []) if item.get("frame_id") == old.frame_id), None)
    if not generated:
        raise VideoProductionError("Regeneration returned no matching asset")
    old.status = "regenerating"
    new_asset = VideoProductionAsset(
        run_id=old.run_id,
        episode_id=old.episode_id,
        frame_id=old.frame_id,
        asset_type=old.asset_type,
        stage=old.stage,
        url=generated.get("url", ""),
        local_path=generated.get("local_path", ""),
        thumbnail_url=generated.get("thumbnail_url", ""),
        duration_seconds=(generated.get("metadata") or {}).get("duration"),
        version=_next_asset_version(db, old.run_id, old.frame_id, old.asset_type),
        metadata_json=generated.get("metadata", {}),
        status="review_pending",
        pixelle_task_id=old.pixelle_task_id,
    )
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    run_ai_audit_for_assets(db, run, [new_asset])
    db.refresh(new_asset)
    return new_asset
```

- [ ] **Step 5: Add regeneration routes**

Add to `server/app/routers/video_production.py`:

```python
@router.post("/assets/{asset_id}/start-regeneration")
async def start_regeneration(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = await start_asset_regeneration(db, asset_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}


@router.post("/assets/{asset_id}/sync-regeneration")
async def sync_regeneration(
    asset_id: str,
    db: Session = Depends(get_db),
    user=Depends(verify_admin_token),
):
    try:
        asset = await sync_regenerated_asset(db, asset_id)
    except VideoProductionError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": _asset_payload(asset)}
```

- [ ] **Step 6: Run regeneration tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_regeneration.py tests/test_video_production_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit regeneration flow**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/services/video_production_service.py server/app/routers/video_production.py server/tests/test_video_production_regeneration.py
git commit -m "feat: add staged asset regeneration"
```

## Task 8: Enrich Review API Payloads

**Files:**

- Modify: `server/app/routers/video_production.py`
- Modify: `server/tests/test_video_production_api.py`

- [ ] **Step 1: Add API payload test**

Append to `server/tests/test_video_production_api.py`:

```python
def test_review_items_include_storyboard_context_and_latest_ai_review(db):
    from app.db_models import Episode, Series, VideoProductionAsset, VideoProductionRun, VideoReviewRecord

    series = Series(title="Payload", logline="Test", genre="drama", target_duration=60)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "narration": "Narration", "reference_urls": ["ref.png"]}]},
    )
    db.add(episode)
    db.flush()
    run = VideoProductionRun(series_id=series.id, episode_id=episode.id, storyboard_json=episode.storyboard_json, model_trace_json={"image_generation": {"provider": "mock"}})
    db.add(run)
    db.flush()
    asset = VideoProductionAsset(run_id=run.id, episode_id=episode.id, frame_id="frame-001", asset_type="image", stage="image_generation", url="image.png", version=1, status="review_pending")
    db.add(asset)
    db.flush()
    db.add(VideoReviewRecord(asset_id=asset.id, run_id=run.id, review_type="ai", status="needs_human", score=0.42, issues_json=["low confidence"]))
    db.commit()

    response = client.get(f"/api/video-production/review-items?run_id={run.id}")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["storyboard_frame"]["image_prompt"] == "Prompt"
    assert item["storyboard_frame"]["narration"] == "Narration"
    assert item["storyboard_frame"]["reference_urls"] == ["ref.png"]
    assert item["latest_ai_review"]["status"] == "needs_human"
    assert item["latest_ai_review"]["issues_json"] == ["low confidence"]
    assert item["model_trace_json"]["image_generation"]["provider"] == "mock"
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_api.py::test_review_items_include_storyboard_context_and_latest_ai_review -q
```

Expected: FAIL because payload fields are missing.

- [ ] **Step 3: Add payload helpers**

In `server/app/routers/video_production.py`, import `VideoReviewRecord` and add:

```python
from app.db_models import VideoProductionAsset, VideoProductionRun, VideoReviewRecord
```

Add helper functions:

```python
def _storyboard_frame(run: VideoProductionRun, frame_id: str) -> dict:
    for index, frame in enumerate((run.storyboard_json or {}).get("frames") or []):
        candidate = str(frame.get("frame_id") or frame.get("id") or f"frame-{index + 1:03d}")
        if candidate == frame_id:
            return frame
    return {}


def _latest_ai_review(db: Session, asset_id: str) -> dict | None:
    row = db.query(VideoReviewRecord).filter(
        VideoReviewRecord.asset_id == asset_id,
        VideoReviewRecord.review_type == "ai",
    ).order_by(VideoReviewRecord.created_at.desc()).first()
    if not row:
        return None
    return {
        "id": row.id,
        "status": row.status,
        "score": row.score,
        "criteria_json": row.criteria_json or [],
        "issues_json": row.issues_json or [],
        "model_trace_json": row.model_trace_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
```

Change `_asset_payload` to accept optional `db` and `run`:

```python
def _asset_payload(asset: VideoProductionAsset, db: Session | None = None, run: VideoProductionRun | None = None) -> dict:
    payload = {
        "id": asset.id,
        "run_id": asset.run_id,
        "episode_id": asset.episode_id,
        "frame_id": asset.frame_id,
        "asset_type": asset.asset_type,
        "stage": asset.stage,
        "url": asset.url,
        "local_path": asset.local_path,
        "thumbnail_url": asset.thumbnail_url,
        "duration_seconds": asset.duration_seconds,
        "version": asset.version,
        "metadata_json": asset.metadata_json or {},
        "status": asset.status,
        "pixelle_task_id": asset.pixelle_task_id,
    }
    if db and run:
        payload["storyboard_frame"] = _storyboard_frame(run, asset.frame_id)
        payload["latest_ai_review"] = _latest_ai_review(db, asset.id)
        payload["model_trace_json"] = run.model_trace_json or {}
    return payload
```

- [ ] **Step 4: Update review item query to pass context**

In `review_items`, after loading `items`, fetch runs:

```python
    run_ids = {item.run_id for item in items}
    runs_by_id = {
        run.id: run
        for run in db.query(VideoProductionRun).filter(VideoProductionRun.id.in_(run_ids)).all()
    } if run_ids else {}
    return {
        "ok": True,
        "items": [_asset_payload(item, db=db, run=runs_by_id.get(item.run_id)) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit enriched review API**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/app/routers/video_production.py server/tests/test_video_production_api.py
git commit -m "feat: enrich video production review payloads"
```

## Task 9: Add Frontend Stage APIs and Production Monitor

**Files:**

- Modify: `web/src/api/videoProduction.js`
- Create: `web/src/views/VideoProductionMonitorPage.vue`
- Modify: `web/src/router/index.js`
- Create: `web/src/__tests__/video-production-monitor-page.test.js`
- Modify: `web/src/__tests__/api-clients.test.js`

- [ ] **Step 1: Add API client tests**

Append to `web/src/__tests__/api-clients.test.js`:

```javascript
it('video production client calls video and compose routes', async () => {
  const {
    startVideoStage,
    syncVideoStage,
    startComposeStage,
    syncComposeStage,
    startAssetRegeneration,
    syncAssetRegeneration,
  } = await import('../api/videoProduction.js')

  await startVideoStage('run-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/start-videos')

  await syncVideoStage('run-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/sync-video-results')

  await startComposeStage('run-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/compose')

  await syncComposeStage('run-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/sync-compose-results')

  await startAssetRegeneration('asset-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/assets/asset-1/start-regeneration')

  await syncAssetRegeneration('asset-1')
  expect(mockPost).toHaveBeenCalledWith('/video-production/assets/asset-1/sync-regeneration')
})
```

- [ ] **Step 2: Run API client test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js
```

Expected: FAIL because functions are missing.

- [ ] **Step 3: Add client functions**

Append to `web/src/api/videoProduction.js`:

```javascript
export function startVideoStage(runId) {
  return client.post(`/video-production/runs/${runId}/start-videos`)
}

export function syncVideoStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-video-results`)
}

export function startComposeStage(runId) {
  return client.post(`/video-production/runs/${runId}/compose`)
}

export function syncComposeStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-compose-results`)
}

export function startAssetRegeneration(assetId) {
  return client.post(`/video-production/assets/${assetId}/start-regeneration`)
}

export function syncAssetRegeneration(assetId) {
  return client.post(`/video-production/assets/${assetId}/sync-regeneration`)
}
```

- [ ] **Step 4: Create production monitor page**

Create `web/src/views/VideoProductionMonitorPage.vue`:

```vue
<template>
  <div class="p-6">
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">Video Production</h1>
        <p class="text-slate-500 text-sm font-mono mt-1">Run {{ runId }}</p>
      </div>
      <button @click="load" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
    </div>

    <div v-if="loading" class="text-slate-400 py-12 text-center">Loading production run...</div>
    <div v-else-if="error" class="text-red-400 py-12 text-center">{{ error }}</div>
    <template v-else-if="run">
      <div class="grid grid-cols-7 gap-2 mb-6">
        <div v-for="step in steps" :key="step.key" class="rounded-lg border px-3 py-2 text-xs"
             :class="stepClass(step)">
          <div class="font-medium">{{ step.label }}</div>
          <div class="mt-1 opacity-70">{{ step.status }}</div>
        </div>
      </div>

      <div class="rounded-lg border border-gray-700/50 p-4 mb-6 bg-slate-900/50">
        <div class="text-sm text-slate-300">Current status: <span class="font-mono">{{ run.status }}</span></div>
        <div class="text-xs text-slate-500 mt-1">Current stage: {{ run.current_stage }}</div>
      </div>

      <div class="flex flex-wrap gap-2">
        <button v-if="run.status === 'image_batch_running'" @click="syncImages" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Sync Images</button>
        <button v-if="run.status === 'image_approved'" @click="startVideos" :disabled="acting" class="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Start Video Segments</button>
        <button v-if="run.status === 'video_batch_running'" @click="syncVideos" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Sync Video Segments</button>
        <button v-if="run.status === 'video_segments_approved'" @click="compose" :disabled="acting" class="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Compose Final Video</button>
        <button v-if="run.status === 'composing'" @click="syncCompose" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Sync Final Video</button>
        <button v-if="needsReview" @click="$router.push(`/ai-video-review?run_id=${run.id}`)" class="bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded-lg text-sm">Open Review Center</button>
      </div>

      <div class="mt-6 rounded-lg border border-gray-700/50 overflow-hidden">
        <div class="px-4 py-3 text-sm text-slate-300 border-b border-gray-700/50">Assets</div>
        <div v-for="asset in assets" :key="asset.id" class="px-4 py-3 text-sm flex gap-4 border-b border-gray-800/60">
          <span class="w-28 text-slate-400">{{ asset.asset_type }}</span>
          <span class="w-28 text-slate-400">{{ asset.frame_id }}</span>
          <span class="w-24" :class="asset.status === 'approved' ? 'text-emerald-400' : 'text-amber-300'">{{ asset.status }}</span>
          <span class="text-slate-500 truncate">{{ asset.url }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  getVideoProductionRun,
  syncImageStage,
  startVideoStage,
  syncVideoStage,
  startComposeStage,
  syncComposeStage,
} from '../api/videoProduction.js'

const route = useRoute()
const runId = route.params.runId
const run = ref(null)
const assets = ref([])
const loading = ref(true)
const acting = ref(false)
const error = ref('')

const needsReview = computed(() => ['image_review_pending', 'image_human_review_required', 'video_review_pending', 'video_human_review_required', 'final_review_pending'].includes(run.value?.status))
const steps = computed(() => [
  { key: 'storyboard', label: 'Storyboarding', status: run.value?.storyboard_json?.frames?.length ? 'ready' : 'missing' },
  { key: 'images', label: 'Images', status: stageStatus(['image_batch_running', 'image_review_pending', 'image_human_review_required', 'image_approved']) },
  { key: 'image_review', label: 'Image Review', status: run.value?.status === 'image_approved' ? 'passed' : needsReview.value ? 'blocked' : 'pending' },
  { key: 'videos', label: 'Video Segments', status: stageStatus(['video_batch_running', 'video_review_pending', 'video_human_review_required', 'video_segments_approved']) },
  { key: 'video_review', label: 'Video Review', status: run.value?.status === 'video_segments_approved' ? 'passed' : 'pending' },
  { key: 'compose', label: 'Compose', status: stageStatus(['composing', 'completed']) },
  { key: 'complete', label: 'Complete', status: run.value?.status === 'completed' ? 'done' : 'pending' },
])

function stageStatus(statuses) {
  return statuses.includes(run.value?.status) ? run.value.status : 'pending'
}

function stepClass(step) {
  if (['passed', 'done', 'completed', 'image_approved', 'video_segments_approved'].includes(step.status)) return 'border-emerald-500/40 bg-emerald-950/30 text-emerald-300'
  if (['blocked', 'image_review_pending', 'image_human_review_required', 'video_review_pending', 'video_human_review_required'].includes(step.status)) return 'border-amber-500/40 bg-amber-950/30 text-amber-300'
  if (['image_batch_running', 'video_batch_running', 'composing'].includes(step.status)) return 'border-sky-500/40 bg-sky-950/30 text-sky-300'
  return 'border-gray-700/50 bg-slate-900/50 text-slate-500'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getVideoProductionRun(runId)
    run.value = data.run
    assets.value = data.assets || []
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load production run'
  } finally {
    loading.value = false
  }
}

async function act(fn) {
  acting.value = true
  error.value = ''
  try {
    await fn()
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Action failed'
  } finally {
    acting.value = false
  }
}

function syncImages() { return act(() => syncImageStage(runId)) }
function startVideos() { return act(() => startVideoStage(runId)) }
function syncVideos() { return act(() => syncVideoStage(runId)) }
function compose() { return act(() => startComposeStage(runId)) }
function syncCompose() { return act(() => syncComposeStage(runId)) }

onMounted(load)
</script>
```

- [ ] **Step 5: Add route**

Modify `web/src/router/index.js` near the pipeline route:

```javascript
{
  path: 'video-production/:runId',
  name: 'VideoProductionMonitor',
  component: () => import('../views/VideoProductionMonitorPage.vue'),
},
```

- [ ] **Step 6: Update series start navigation**

In `web/src/views/SeriesDetailPage.vue`, replace:

```javascript
router.push(`/ai-video-review?run_id=${data.run.id}`)
```

with:

```javascript
router.push(`/video-production/${data.run.id}`)
```

- [ ] **Step 7: Add monitor tests**

Create `web/src/__tests__/video-production-monitor-page.test.js`:

```javascript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import VideoProductionMonitorPage from '../views/VideoProductionMonitorPage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { runId: 'run-1' } }),
}))

const api = vi.hoisted(() => ({
  getVideoProductionRun: vi.fn(),
  syncImageStage: vi.fn(),
  startVideoStage: vi.fn(),
  syncVideoStage: vi.fn(),
  startComposeStage: vi.fn(),
  syncComposeStage: vi.fn(),
}))

vi.mock('../api/videoProduction.js', () => api)

describe('VideoProductionMonitorPage', () => {
  it('shows status steps and starts video stage when images are approved', async () => {
    api.getVideoProductionRun.mockResolvedValue({
      data: {
        ok: true,
        run: { id: 'run-1', status: 'image_approved', current_stage: 'image_review', storyboard_json: { frames: [{}] } },
        assets: [],
      },
    })
    api.startVideoStage.mockResolvedValue({ data: { ok: true } })

    const wrapper = mount(VideoProductionMonitorPage, { global: { mocks: { $router: { push: vi.fn() } } } })
    await Promise.resolve()
    await Promise.resolve()

    expect(wrapper.text()).toContain('Video Production')
    expect(wrapper.text()).toContain('Start Video Segments')
    await wrapper.findAll('button').find(btn => btn.text() === 'Start Video Segments').trigger('click')
    expect(api.startVideoStage).toHaveBeenCalledWith('run-1')
  })
})
```

- [ ] **Step 8: Run frontend tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/video-production-monitor-page.test.js src/__tests__/series-detail-video-production.test.js
```

Expected: PASS.

- [ ] **Step 9: Commit frontend monitor**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/api/videoProduction.js web/src/views/VideoProductionMonitorPage.vue web/src/router/index.js web/src/views/SeriesDetailPage.vue web/src/__tests__/api-clients.test.js web/src/__tests__/video-production-monitor-page.test.js web/src/__tests__/series-detail-video-production.test.js
git commit -m "feat: add staged video production monitor"
```

## Task 10: Expand Review Center for All Stage Assets

**Files:**

- Modify: `web/src/views/AIVideoReviewPage.vue`
- Modify: `web/src/__tests__/ai-video-review-page.test.js`

- [ ] **Step 1: Add review center tests**

Add to `web/src/__tests__/ai-video-review-page.test.js`:

```javascript
it('shows storyboard context, AI review issues, and regeneration action', async () => {
  api.listReviewItems.mockResolvedValue({
    data: {
      ok: true,
      items: [{
        id: 'asset-1',
        run_id: 'run-1',
        frame_id: 'frame-001',
        asset_type: 'video_segment',
        stage: 'video_rendering',
        status: 'review_pending',
        version: 2,
        url: 'segment.mp4',
        storyboard_frame: {
          image_prompt: 'Image prompt',
          narration: 'Narration text',
          reference_urls: ['ref.png'],
        },
        latest_ai_review: {
          status: 'needs_human',
          score: 0.42,
          issues_json: ['low confidence'],
        },
        model_trace_json: { video_rendering: { provider: 'mock', model_name: 'mock-video' } },
      }],
    },
  })
  api.getVideoProductionRun.mockResolvedValue({ data: { ok: true, run: { status: 'video_review_pending' } } })

  const wrapper = mount(AIVideoReviewPage)
  await Promise.resolve()
  await Promise.resolve()

  expect(wrapper.text()).toContain('video_segment')
  expect(wrapper.text()).toContain('Image prompt')
  expect(wrapper.text()).toContain('Narration text')
  expect(wrapper.text()).toContain('low confidence')
  expect(wrapper.text()).toContain('mock-video')
  expect(wrapper.text()).toContain('Regenerate')
})

it('does not show unsupported regeneration action for final video assets', async () => {
  api.listReviewItems.mockResolvedValue({
    data: {
      ok: true,
      items: [{
        id: 'asset-final',
        run_id: 'run-1',
        frame_id: 'final',
        asset_type: 'final_video',
        stage: 'composition',
        status: 'review_pending',
        version: 1,
        url: 'final.mp4',
        storyboard_frame: {},
        latest_ai_review: { status: 'needs_human', score: 0.4, issues_json: ['bad cut'] },
        model_trace_json: {},
      }],
    },
  })
  api.getVideoProductionRun.mockResolvedValue({ data: { ok: true, run: { status: 'final_review_pending' } } })

  const wrapper = mount(AIVideoReviewPage)
  await Promise.resolve()
  await Promise.resolve()

  expect(wrapper.text()).toContain('final_video')
  expect(wrapper.text()).not.toContain('Regenerate')
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/ai-video-review-page.test.js
```

Expected: FAIL because UI does not show context or regenerate.

- [ ] **Step 3: Import regeneration APIs**

In `web/src/views/AIVideoReviewPage.vue`, change the import:

```javascript
import {
  getVideoProductionRun,
  listReviewItems,
  reviewAsset,
  startAssetRegeneration,
  syncAssetRegeneration,
  syncImageStage,
} from '../api/videoProduction.js'
```

- [ ] **Step 4: Add context panels**

Inside the selected asset template after the metadata `<dl>`, add:

```vue
<div class="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-5 text-sm">
  <section class="rounded-lg border border-gray-700/50 p-3 bg-slate-950/40">
    <h3 class="text-slate-200 font-medium mb-2">Storyboard</h3>
    <p class="text-slate-400 whitespace-pre-wrap">{{ selected.storyboard_frame?.image_prompt || 'No prompt' }}</p>
    <p class="text-slate-500 mt-2 whitespace-pre-wrap">{{ selected.storyboard_frame?.narration || 'No narration' }}</p>
    <div class="mt-2 text-xs text-slate-500 break-all">
      <div v-for="url in selected.storyboard_frame?.reference_urls || []" :key="url">{{ url }}</div>
    </div>
  </section>
  <section class="rounded-lg border border-gray-700/50 p-3 bg-slate-950/40">
    <h3 class="text-slate-200 font-medium mb-2">AI Review</h3>
    <p class="text-slate-400">Status: {{ selected.latest_ai_review?.status || 'none' }}</p>
    <p class="text-slate-400">Score: {{ selected.latest_ai_review?.score ?? '-' }}</p>
    <ul class="mt-2 text-xs text-amber-300 space-y-1">
      <li v-for="issue in selected.latest_ai_review?.issues_json || []" :key="issue">{{ issue }}</li>
    </ul>
  </section>
  <section class="rounded-lg border border-gray-700/50 p-3 bg-slate-950/40">
    <h3 class="text-slate-200 font-medium mb-2">Model Trace</h3>
    <pre class="text-xs text-slate-400 whitespace-pre-wrap">{{ JSON.stringify(selected.model_trace_json || {}, null, 2) }}</pre>
  </section>
</div>
```

- [ ] **Step 5: Add media preview switch**

Replace the preview block with:

```vue
<div class="aspect-video rounded-lg border border-gray-700/50 bg-slate-950/80 mb-4 overflow-hidden flex items-center justify-center">
  <video v-if="selected.asset_type !== 'image' && selected.url" :src="selected.url" controls class="max-h-full max-w-full"></video>
  <img v-else-if="selected.url" :src="selected.url" :alt="selected.frame_id" class="max-h-full max-w-full object-contain" />
  <span v-else class="text-sm text-slate-500">No preview URL</span>
</div>
```

- [ ] **Step 6: Add regenerate actions**

Add button:

```vue
<button v-if="selected.asset_type !== 'final_video'" @click="regenerate" :disabled="acting" class="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
  Regenerate
</button>
<button v-if="selected.asset_type !== 'final_video' && selected.status === 'regenerating'" @click="syncRegen" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
  Sync Regeneration
</button>
```

Add script functions:

```javascript
async function regenerate() {
  if (!selected.value) return
  acting.value = true
  try {
    await startAssetRegeneration(selected.value.id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to start regeneration'
  } finally {
    acting.value = false
  }
}

async function syncRegen() {
  if (!selected.value) return
  acting.value = true
  try {
    await syncAssetRegeneration(selected.value.id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to sync regeneration'
  } finally {
    acting.value = false
  }
}
```

- [ ] **Step 7: Run review center tests**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/ai-video-review-page.test.js
```

Expected: PASS.

- [ ] **Step 8: Commit review center expansion**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add web/src/views/AIVideoReviewPage.vue web/src/__tests__/ai-video-review-page.test.js
git commit -m "feat: expand AI video review center"
```

## Task 11: Add Full Mocked E2E

**Files:**

- Create: `server/tests/test_video_production_full_mocked_e2e.py`

- [ ] **Step 1: Write E2E test**

Create `server/tests/test_video_production_full_mocked_e2e.py`:

```python
from fastapi.testclient import TestClient

from app.db_models import Episode, GeneratedVideo, Series
from app.main import app


client = TestClient(app)


def test_storyboard_to_final_video_mocked_e2e(db, monkeypatch):
    series = Series(title="Full E2E", logline="Test", genre="drama", target_duration=30)
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        title="Pilot",
        storyboard_json={"frames": [{"frame_id": "frame-001", "image_prompt": "Prompt", "video_prompt": "Move", "narration": "Hello", "duration": 5}]},
    )
    db.add(episode)
    db.commit()

    stage = {"current": None}

    async def fake_submit_image_batch(db, run_id, episode_id, frames, model_config, template_config=None):
        stage["current"] = "image"
        return {"ok": True, "stage_task_id": "image-task"}

    async def fake_submit_video_batch(db, run_id, frames, model_config, template_config=None):
        stage["current"] = "video"
        return {"ok": True, "stage_task_id": "video-task"}

    async def fake_submit_compose(db, run_id, segments, edit_manifest, model_config=None):
        stage["current"] = "compose"
        return {"ok": True, "stage_task_id": "compose-task"}

    async def fake_get_stage_task(db, stage_task_id):
        if stage_task_id == "image-task":
            return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001", "asset_type": "image", "url": "image.png", "metadata": {"duration": 5}}]}
        if stage_task_id == "video-task":
            return {"ok": True, "status": "completed", "assets": [{"frame_id": "frame-001", "asset_type": "video_segment", "url": "segment.mp4", "metadata": {"duration": 5}}]}
        return {"ok": True, "status": "completed", "assets": [{"frame_id": "final", "asset_type": "final_video", "url": "final.mp4", "local_path": "output/final.mp4", "metadata": {"duration": 5}}]}

    monkeypatch.setattr("app.services.video_production_service.resolve_runtime_model_config", lambda db, scene: {"provider": "mock", "api_key": "x", "scene_key": scene})
    monkeypatch.setattr("app.services.video_production_service.submit_image_batch", fake_submit_image_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_video_batch", fake_submit_video_batch)
    monkeypatch.setattr("app.services.video_production_service.submit_compose", fake_submit_compose)
    monkeypatch.setattr("app.services.video_production_service.get_stage_task", fake_get_stage_task)
    monkeypatch.setattr("app.routers.audit._do_audit", lambda model, url, text: {"score": 0.99, "pass_fail": True, "issues": []})

    created = client.post("/api/video-production/runs", json={"series_id": series.id, "episode_id": episode.id}).json()
    run_id = created["run"]["id"]

    assert client.post(f"/api/video-production/runs/{run_id}/start-images").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-image-results").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/start-videos").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-video-results").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/compose").status_code == 200
    assert client.post(f"/api/video-production/runs/{run_id}/sync-compose-results").status_code == 200

    final = client.get(f"/api/video-production/runs/{run_id}").json()
    assert final["run"]["status"] == "completed"
    db.refresh(episode)
    assert episode.video_url == "final.mp4"
    assert episode.status == "done"
    assert db.query(GeneratedVideo).filter_by(pixelle_task_id=run_id).count() == 1
```

- [ ] **Step 2: Run E2E test to verify failure or pass after prior tasks**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_full_mocked_e2e.py -q
```

Expected after Tasks 1-10: PASS.

- [ ] **Step 3: Run backend production suite**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_state_machine.py tests/test_video_production_video_stage.py tests/test_video_production_compose.py tests/test_video_production_regeneration.py tests/test_video_production_api.py tests/test_video_production_full_mocked_e2e.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit E2E**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add server/tests/test_video_production_full_mocked_e2e.py
git commit -m "test: add full mocked staged production e2e"
```

## Task 12: Final Verification and Documentation Sync

**Files:**

- Modify: `docs/superpowers/reports/2026-05-25-dy-auto-pixelle-phase0-image-wedge-implementation-review.md` if it is kept as a current status report.
- Create: `docs/superpowers/reports/2026-05-25-dy-auto-pixelle-stage-gated-full-implementation-verification.md`

- [ ] **Step 1: Run dy_auto backend verification**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_models.py tests/test_pipeline_saved_storyboard_compat.py tests/test_pixelle_config_security.py tests/test_audit_gate.py tests/test_runtime_model_config.py tests/test_pixelle_stage_client.py tests/test_video_production_service.py tests/test_video_production_api.py tests/test_video_production_state_machine.py tests/test_video_production_video_stage.py tests/test_video_production_compose.py tests/test_video_production_regeneration.py tests/test_video_production_full_mocked_e2e.py -q
```

Expected: PASS.

- [ ] **Step 2: Run dy_auto frontend verification**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/video-production-monitor-page.test.js
```

Expected: PASS.

- [ ] **Step 3: Run Pixelle stage verification**

Run:

```powershell
cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_stage_runtime_config.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py tests/test_files_security.py -q
```

Expected: PASS.

- [ ] **Step 4: Run diff checks**

Run:

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git diff --check

cd D:\devWorkspace\Pixelle-Video
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 5: Write verification report**

Create `docs/superpowers/reports/2026-05-25-dy-auto-pixelle-stage-gated-full-implementation-verification.md` with:

~~~markdown
# dy_auto + Pixelle Stage-Gated Full Implementation Verification

Date: 2026-05-25

## Result

- dy_auto backend: PASS
- dy_auto frontend: PASS
- Pixelle stage APIs: PASS
- diff check: PASS

## Covered Flow

storyboard -> images -> image AI review -> image approval -> video segments -> video AI review -> video approval -> compose -> final video library.

## Commands

```powershell
cd D:\devWorkspace\jsProjects\dy_auto\server
pytest tests/test_video_production_models.py tests/test_pipeline_saved_storyboard_compat.py tests/test_pixelle_config_security.py tests/test_audit_gate.py tests/test_runtime_model_config.py tests/test_pixelle_stage_client.py tests/test_video_production_service.py tests/test_video_production_api.py tests/test_video_production_state_machine.py tests/test_video_production_video_stage.py tests/test_video_production_compose.py tests/test_video_production_regeneration.py tests/test_video_production_full_mocked_e2e.py -q

cd D:\devWorkspace\jsProjects\dy_auto\web
npx vitest run src/__tests__/api-clients.test.js src/__tests__/series-detail-video-production.test.js src/__tests__/ai-video-review-page.test.js src/__tests__/video-production-monitor-page.test.js

cd D:\devWorkspace\Pixelle-Video
python -m pytest tests/test_stage_api_auth.py tests/test_stage_images_api.py tests/test_stage_videos_api.py tests/test_stage_compose_api.py tests/test_files_security.py -q
```
~~~

- [ ] **Step 6: Commit verification report**

```powershell
cd D:\devWorkspace\jsProjects\dy_auto
git add docs/superpowers/reports/2026-05-25-dy-auto-pixelle-stage-gated-full-implementation-verification.md
git commit -m "docs: add staged video production verification report"
```

## Self-Review

### Spec Coverage

- dy_auto orchestration layer: Tasks 3, 5, 6, 7, 8, 9, 10, 11.
- Pixelle execution stage APIs: Tasks 1 and 2.
- Runtime model config delivery: Tasks 4, 5, and 6 reuse `resolve_runtime_model_config` and redacted model trace.
- Generated images, video segments, final videos: Tasks 5 and 6.
- AI and human review gates: Tasks 3, 5, 8, and 10.
- Single-item regeneration: Task 7 and Task 10.
- Review center frontend: Task 10.
- Episode status strip / production visibility: Task 9.
- Final video library: Task 6 and Task 11.
- Full mocked E2E: Task 11.
- Pixelle auth/file safety: Task 1 and Task 2 verification set.

### Placeholder Scan

This plan intentionally avoids open-ended placeholder instructions. Every task names files, test code, implementation code, commands, and expected outcomes.

### Type Consistency

- Asset types used consistently: `image`, `video_segment`, `final_video`.
- Stages used consistently: `image_generation`, `video_rendering`, `composition`.
- Run statuses used consistently: `storyboard_ready`, `image_batch_running`, `image_review_pending`, `image_human_review_required`, `image_approved`, `video_batch_running`, `video_review_pending`, `video_human_review_required`, `video_segments_approved`, `composing`, `final_review_pending`, `completed`, `failed`.
- Route names match frontend client names:
  - `/start-images` -> `startImageStage`
  - `/sync-image-results` -> `syncImageStage`
  - `/start-videos` -> `startVideoStage`
  - `/sync-video-results` -> `syncVideoStage`
  - `/compose` -> `startComposeStage`
  - `/sync-compose-results` -> `syncComposeStage`

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | NOT_RUN | Not required for this engineering pass. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | NOT_RUN | Not run in this pass. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR_AFTER_REVISION | 9 findings addressed in plan body. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | NOT_RUN | UI scope exists; design review remains useful before implementation. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT_RUN | Not required before implementation. |

### Resolved Engineering Findings

- Runtime model config is now covered by Task 2A with `stage_runtime_config.py`, redaction tests, and image/video/compose stage usage.
- The missing direct compose dependency is removed; Task 2A adds `stage_compose.py` wrapping existing post-production composition.
- Video segment regeneration now uses `video_stage_frame_for_asset(db, run, asset.frame_id)` and includes a second-frame regeneration test.
- Final composition now runs a final audit gate and enters `final_review_pending` when audit fails instead of writing directly to `GeneratedVideo`.
- Stage API tests now poll task status until completion before asserting returned assets.
- Mock MP4 generation now uses ffmpeg to create a playable tiny MP4 instead of writing a header-only byte string.
- Stage task history is preserved through `record_stage_task(...)` in `model_trace_json["stage_tasks"]`.
- `GeneratedVideo.keyword` now uses a non-empty fallback: `episode.title or series.title or run.id`.
- Partial frame failure metadata is represented in `StageAsset` and persisted as failed video assets with retry metadata.

### Remaining Caveats

- Paid-provider E2E is still outside the implementation gate; run it manually once real Seedance/Kling/Wan credentials are configured.
- The plan still includes significant frontend work; run `/plan-design-review` before implementation if visual review quality matters for the review center and monitor.

### Parallelization Strategy

| Lane | Work | Depends on |
|---|---|---|
| Lane A | Pixelle stage contracts, runtime model adapter, compose adapter | None |
| Lane B | dy_auto state machine, idempotency, stage task tracking | None |
| Lane C | dy_auto video/compose service and routes | Lane A API shape + Lane B gates |
| Lane D | Frontend monitor and review center | Lane C response contracts |
| Lane E | Full mocked E2E and verification report | Lanes A-D |

Execution recommendation: run Lane A and Lane B in parallel, merge contracts, then run Lane C, then Lane D, then Lane E.

### Completion Summary

- Step 0 Scope Challenge: scope accepted as full stage-gated implementation.
- Architecture Review: 5 issues found, all addressed in the plan.
- Code Quality Review: 2 issues found, both addressed in the plan.
- Test Review: 2 gaps identified, both addressed in the plan.
- Performance Review: 0 issues found in this pass.
- NOT in scope: written.
- What already exists: written in file map and resolved findings.
- Failure modes: 5 listed and addressed in revised tasks.
- Outside voice: skipped.
- Parallelization: 5 lanes, 2 initial parallel lanes.
- Verdict: CLEAR_AFTER_REVISION. Ready for implementation planning/execution.

## GSTACK ENG REVIEW ROUND 2

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Second-pass architecture, state, test, and integration review | 2 | CLEAR_AFTER_REVISION_ROUND_2 | 7 findings addressed in plan body. |

### Resolved Round 2 Findings

1. `[P0] (confidence: 9/10) lines 1015-1040, 1089, 1849-1880` — Final human approval cannot complete a failed final audit. `run_final_audit_for_asset` can leave the run in `final_review_pending`, but `approve_asset` still calls `recompute_run_gate(db, asset.run_id, asset.asset_type)`, and `recompute_run_gate` rejects any asset type except `image` and `video_segment`. A final video that needs human approval therefore cannot write `Episode.video_url` or `GeneratedVideo`.
   - Plan revision: Task 6 adds `approve_final_video_asset(...)` and `reject_final_video_asset(...)`; approval writes final video records, rejection returns the run to compose-ready.
   - Plan tests: `test_human_approve_final_video_completes_run_after_final_audit_failure` and `test_human_reject_final_video_returns_run_to_compose_ready`.

2. `[P1] (confidence: 9/10) lines 1455-1488 vs existing image sync path` — Video sync is idempotent, but image sync is still not. `mark_video_stage_assets` checks existing assets for the same run/type/task, while the existing image path is not revised to do the same. Double-syncing image results can create a newer `review_pending` image version for an already-approved frame and reopen/block the run.
   - Plan revision: Task 3 adds an existing-task guard to `mark_image_stage_assets` and skips duplicate AI review records.
   - Plan test: `test_sync_image_stage_results_is_idempotent_for_same_pixelle_task` and `test_ai_audit_is_idempotent_for_existing_asset_review`.

3. `[P1] (confidence: 8/10) lines 991-997, 1422-1438, 1781-1799` — Start gates do not prevent duplicate video or compose submissions. `assert_can_start_videos` only checks approved images, and `assert_can_compose` only checks approved segments; neither rejects `video_batch_running`, `composing`, or an existing in-flight stage task. Rapid double-clicks or retrying the same action can create duplicate Pixelle jobs and overwrite `pixelle_stage_task_id`.
   - Plan revision: Task 3 makes `assert_can_start_videos` and `assert_can_compose` status-aware.
   - Plan tests: `test_start_video_stage_rejects_duplicate_inflight_run` and `test_start_compose_stage_rejects_duplicate_inflight_run`.

4. `[P1] (confidence: 9/10) lines 284-302 plus server/app/services/runtime_model_config.py:26-35` — Runtime model config fields do not line up. dy_auto sends provider settings under `config`, but Pixelle `stage_media_kwargs` only reads `parameters`, `workflow`, and `default_workflow` at the top level. Default duration, resolution, workflow, and provider-specific fields from the AI model center will silently be ignored for real providers.
   - Plan revision: Task 2A now merges `config`, `config_json`, and `parameters`, maps default workflow/duration/resolution/aspect ratio, and derives width/height from `1080x1920`.
   - Plan test: `test_stage_media_kwargs_accepts_dy_auto_resolve_runtime_model_config_shape`.

5. `[P1] (confidence: 8/10) lines 574-577, 685-719, 3184` — The plan claims partial frame failures are handled, but `StageFrameError` is declared and never used. `_run_video_batch` does not catch per-frame provider failures, so one failed frame fails the whole task instead of returning a failed frame asset with retry metadata.
   - Plan revision: Task 2 wraps each video frame render in `try/except` and returns failed `StageAsset` metadata generated from `StageFrameError`.
   - Plan test: `test_video_batch_records_per_frame_failure_without_failing_whole_task`.

6. `[P1] (confidence: 9/10) lines 48, 2189-2221` — Regeneration does not re-run AI review even though the success criteria require it. `sync_regenerated_asset` creates the next version and recomputes the gate, but never calls `run_ai_audit_for_assets`, so the new version has no AI review record.
   - Plan revision: Task 7 now calls `run_ai_audit_for_assets(db, run, [new_asset])` after regenerated asset persistence.
   - Plan tests: regenerated image and regenerated video segment each create a new `VideoReviewRecord(review_type="ai")`.

7. `[P2] (confidence: 8/10) lines 2800-2850 plus unsupported final regeneration branch at 2140-2171` — The review center shows `Regenerate` for every selected asset, but backend regeneration only supports `image` and `video_segment`. A `final_video` review item will offer an action that always fails.
   - Plan revision: Task 10 hides regenerate and sync regeneration actions for `final_video`.
   - Plan test: `test_does_not_show_unsupported_regeneration_action_for_final_video_assets`.

### Test Coverage Diagram

```text
 dy_auto state gates
  + start images                       [COVERED IN PLAN] image sync idempotency
  + start videos                       [COVERED IN PLAN] duplicate in-flight submission
  + start compose                      [COVERED IN PLAN] duplicate in-flight submission
  + final approval                     [COVERED IN PLAN] final_video human approval completion

 Pixelle stage execution
  + image batch                        [COVERED IN PLAN] real config shape from dy_auto
  + video batch                        [COVERED IN PLAN] per-frame provider failure
  + compose                            [COVERED IN PLAN] final audit and final human pass

 Review and regeneration
  + image/video review payload         [COVERED IN PLAN]
  + asset regeneration                 [COVERED IN PLAN] regenerated version AI review record
  + final video review UI              [COVERED IN PLAN] unsupported regenerate action hidden
```

### NOT In Scope

- Paid-provider online E2E remains manual after real credentials are configured.
- Douyin publishing remains outside this plan.
- Visual timeline editing remains outside this plan.

### What Already Exists

- Existing `VideoProductionRun`, `VideoProductionAsset`, and `VideoReviewRecord` are reused correctly as the stage truth model.
- Existing AI model center resolver is reused, and Task 2A now consumes its actual payload shape.
- Existing review route is reused, and Task 6 now adds a dedicated final-video completion branch.
- Existing Pixelle stage task manager is reused, and Task 2 now handles per-frame video failures inside batch workers.

### Failure Modes

| Failure Mode | Covered In Revised Plan | Plan Coverage |
|---|---:|---|
| Final audit fails and human approves or rejects final asset | Yes | Complete final writeback on approval; return to compose-ready on rejection. |
| User double-clicks start video or compose | Yes | Status/task guard and regression tests. |
| User double-clicks sync image results | Yes | Idempotent image asset persistence and duplicate audit skip. |
| Real provider fails one frame in a batch | Yes | Per-frame failed asset and retry metadata. |
| Regenerated asset needs AI review history | Yes | Audit call and review record assertion. |

### Parallelization Update

| Lane | Work | Depends on |
|---|---|---|
| Lane A | Pixelle config-shape adapter and per-frame failure handling | None |
| Lane B | dy_auto state/idempotency/final approval fixes | None |
| Lane C | Review center final-video action correction | Lane B contract |
| Lane D | Missing regression tests and full mocked E2E update | Lanes A-C |

Execution recommendation: run Lane A and Lane B in parallel, then Lane C, then Lane D.

### Completion Summary

- Step 0 Scope Challenge: scope still accepted as full stage-gated implementation; no scope reduction recommended.
- Architecture Review: 4 issues found, all addressed in the plan.
- Code Quality Review: 1 issue found, addressed in the plan.
- Test Review: diagram produced, 6 gaps identified, all addressed in the plan.
- Performance Review: 0 issues found.
- NOT in scope: written.
- What already exists: written.
- TODOS.md updates: 0 proposed; these are blocking plan revisions, not deferred TODOs.
- Failure modes: 5 critical/important gaps flagged and addressed.
- Outside voice: skipped.
- Parallelization: 4 lanes, 2 initial parallel lanes.
- Verdict: CLEAR_AFTER_REVISION_ROUND_2. Ready for implementation planning/execution.
