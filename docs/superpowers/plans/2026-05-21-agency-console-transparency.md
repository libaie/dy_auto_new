# Agency Console Transparency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only expert-team transparency console that shows which embedded experts participate in each automated video production step and what the backend actually did.

**Architecture:** Add a backend aggregation endpoint for `GET /api/series/{series_id}/agency-console`, enrich pipeline layer records with safe execution summaries, and render a new Vue page that reads one structured payload. Keep the existing generation flow unchanged.

**Tech Stack:** FastAPI, SQLAlchemy, JSON columns, Vue 3 Composition API, Vitest, pytest.

---

## File Structure

- Create: `server/app/services/agency_console.py`
  - Builds production steps from `Series`, `Episode`, `PipelineRun`, `GeneratedVideo`, `style_lock`, and layer summaries.
- Modify: `server/app/routers/series.py`
  - Adds `GET /api/series/{series_id}/agency-console`.
- Modify: `server/app/routers/pipeline.py`
  - Adds safe `input_summary`, `output_summary`, `agency_roles`, and `quality_gates` to each layer entry.
- Create: `server/tests/test_agency_console.py`
  - Backend coverage for aggregation endpoint and pipeline summaries.
- Modify: `web/src/api/series.js`
  - Adds `getAgencyConsole(seriesId)`.
- Modify: `web/src/router/index.js`
  - Adds `/series/:seriesId/agency-console`.
- Create: `web/src/views/AgencyConsolePage.vue`
  - Read-only expert-team and production-process console.
- Modify: `web/src/views/SeriesDetailPage.vue`
  - Adds entry button to the console.
- Modify: `web/src/views/PipelineMonitorPage.vue`
  - Adds entry button to the console when `run.series_id` exists.
- Modify: `web/src/__tests__/api-clients.test.js`
  - Adds API client coverage.
- Create: `web/src/__tests__/agency-console-page.test.js`
  - Component coverage for display behavior.

## Task 1: Backend Agency Console Service

**Files:**
- Create: `server/app/services/agency_console.py`
- Test: `server/tests/test_agency_console.py`

- [ ] **Step 1: Write the failing endpoint test**

Add this test to `server/tests/test_agency_console.py`:

```python
from fastapi.testclient import TestClient

from app.main import app
from app.db_models import Episode, Series


def test_agency_console_returns_pending_steps_without_style_lock(db):
    client = TestClient(app)
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    db.add(Episode(series_id=series.id, episode_number=1, status="pending"))
    db.commit()

    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["style_lock"]["locked"] is False
    assert data["agency_team_status"]["core_role_count"] == 5
    assert data["production_steps"][0]["id"] == "input"
    assert any(step["id"] == "style_lock" and step["status"] == "pending" for step in data["production_steps"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py::test_agency_console_returns_pending_steps_without_style_lock -q
```

Expected: `404` for `/api/series/{series_id}/agency-console` or import failure because the service does not exist yet.

- [ ] **Step 3: Implement the service skeleton**

Create `server/app/services/agency_console.py` with:

```python
"""Read-only transparency payload for automated video production."""
from __future__ import annotations

from typing import Any

from app.db_models import Episode, GeneratedVideo, PipelineRun, Series
from app.services.video_agency_team import ensure_video_agency_team, summarize_video_agency_team


LAYER_LABELS = {
    0: ("layer_0_assets", "L0 图像资产生成", "render"),
    1: ("layer_1_narration", "L1 旁白生成", "storyboard"),
    2: ("layer_2_title", "L2 标题生成", "storyboard"),
    3: ("layer_3_image_prompt", "L3 图像提示词生成", "render"),
    4: ("layer_4_render", "L4 视频渲染", "render"),
    5: ("layer_5_postproduction", "L5 后期剪辑", "final_edit"),
}


def _safe_text(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _gate_list(team: dict, phase: str) -> list[str]:
    gates = team.get("quality_gates") or {}
    return list(gates.get(phase, []))


def _roles_for_phase(team: dict, phase: str) -> list[str]:
    roles = []
    for role in list(team.get("core_roles") or []) + list(team.get("support_roles") or []):
        if phase in (role.get("phase") or []):
            roles.append(role.get("id"))
    return [role_id for role_id in roles if role_id]


def _step(step_id: str, label: str, status: str, phase: str, team: dict,
          input_summary: dict | None = None, output_summary: dict | None = None,
          persistence: list[str] | None = None, error: str = "") -> dict:
    return {
        "id": step_id,
        "label": label,
        "status": status,
        "phase": phase,
        "agency_roles": _roles_for_phase(team, phase),
        "quality_gates": _gate_list(team, phase),
        "input_summary": input_summary or {},
        "output_summary": output_summary or {},
        "persistence": persistence or [],
        "error": _safe_text(error, 500),
    }


def build_agency_console_payload(series: Series, episodes: list[Episode],
                                 latest_run: PipelineRun | None,
                                 generated_video: GeneratedVideo | None) -> dict:
    story_bible = series.story_bible_json or {}
    style_lock = story_bible.get("style_lock", {}) if isinstance(story_bible, dict) else {}
    team = ensure_video_agency_team(style_lock if isinstance(style_lock, dict) else {})
    current_episode = episodes[0] if episodes else None
    if latest_run and latest_run.episode_id:
        current_episode = next((ep for ep in episodes if ep.id == latest_run.episode_id), current_episode)

    steps = [
        _step(
            "input",
            "输入系列一句话",
            "completed" if series.logline else "pending",
            "style_lock",
            team,
            output_summary={"title": series.title, "logline": _safe_text(series.logline)},
            persistence=["Series.title", "Series.logline"],
        ),
        _step(
            "style_lock",
            "风格锁定",
            "completed" if bool(style_lock.get("locked")) else "pending",
            "style_lock",
            team,
            input_summary={"genre": series.genre, "target_duration": series.target_duration},
            output_summary={
                "version": style_lock.get("version", 0),
                "character_count": len(style_lock.get("characters") or []),
                "scene_count": len(style_lock.get("scenes") or []),
                "missing_asset_count": len(style_lock.get("missing_assets") or []),
            },
            persistence=["Series.story_bible_json.style_lock"],
        ),
    ]

    storyboard = current_episode.storyboard_json if current_episode else {}
    frames = storyboard.get("frames", []) if isinstance(storyboard, dict) else []
    steps.append(_step(
        "auto_plan",
        "自动分镜",
        "completed" if frames else "pending",
        "storyboard",
        team,
        input_summary={"style_lock_version": style_lock.get("version", 0), "target_duration": series.target_duration},
        output_summary={"frame_count": len(frames), "total_duration": storyboard.get("total_duration", 0) if isinstance(storyboard, dict) else 0},
        persistence=["Episode.storyboard_json"],
    ))

    layers = latest_run.layers_json or {} if latest_run else {}
    for index, (step_id, label, phase) in LAYER_LABELS.items():
        layer = layers.get(str(index)) or {}
        steps.append(_step(
            step_id,
            label,
            layer.get("status") or ("running" if latest_run and latest_run.current_layer == index else "pending"),
            phase,
            team,
            input_summary=layer.get("input_summary") or {},
            output_summary=layer.get("output_summary") or {},
            persistence=["PipelineRun.layers_json"],
            error=layer.get("error") or "",
        ))

    steps.append(_step(
        "episode_writeback",
        "写回剧集",
        "completed" if current_episode and current_episode.video_url else "pending",
        "final_edit",
        team,
        output_summary={"video_url": current_episode.video_url if current_episode else "", "status": current_episode.status if current_episode else ""},
        persistence=["Episode.video_url", "Episode.duration_seconds", "Episode.status"],
    ))
    steps.append(_step(
        "video_library_writeback",
        "写入视频资产库",
        "completed" if generated_video and generated_video.video_path else "pending",
        "final_edit",
        team,
        output_summary={"video_path": generated_video.video_path if generated_video else "", "status": generated_video.status if generated_video else ""},
        persistence=["GeneratedVideo"],
    ))

    return {
        "ok": True,
        "series": {"id": series.id, "title": series.title, "logline": series.logline},
        "style_lock": {
            "locked": bool(style_lock.get("locked")),
            "version": style_lock.get("version", 0),
            "missing_assets": style_lock.get("missing_assets", []),
        },
        "agency_team": team,
        "agency_team_status": summarize_video_agency_team(team),
        "current_episode": {
            "id": current_episode.id,
            "episode_number": current_episode.episode_number,
            "title": current_episode.title,
            "status": current_episode.status,
        } if current_episode else None,
        "latest_run": {
            "id": latest_run.id,
            "status": latest_run.status,
            "current_layer": latest_run.current_layer,
        } if latest_run else None,
        "production_steps": steps,
        "generated_video": {
            "id": generated_video.id,
            "video_path": generated_video.video_path,
            "status": generated_video.status,
        } if generated_video else None,
    }
```

- [ ] **Step 4: Add the endpoint**

In `server/app/routers/series.py`, import:

```python
from app.db_models import GeneratedVideo
from app.services.agency_console import build_agency_console_payload
```

If `GeneratedVideo` is already imported elsewhere in the file after concurrent edits, keep a single import.

Add this route after `get_style_lock`:

```python
@router.get("/{series_id}/agency-console")
def get_agency_console(series_id: str, db: Session = Depends(get_db),
                       _: str = Depends(verify_admin_token)):
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise HTTPException(404, "Series not found")
    episodes = db.query(Episode).filter(
        Episode.series_id == series_id
    ).order_by(Episode.episode_number).all()
    latest_run = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id
    ).order_by(PipelineRun.created_at.desc()).first()
    generated_video = None
    if latest_run:
        generated_video = db.query(GeneratedVideo).filter(
            GeneratedVideo.pixelle_task_id == latest_run.id
        ).first()
    return build_agency_console_payload(series, episodes, latest_run, generated_video)
```

- [ ] **Step 5: Verify Task 1 passes**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py::test_agency_console_returns_pending_steps_without_style_lock -q
```

Expected: `1 passed`.

## Task 2: Pipeline Layer Transparency Summaries

**Files:**
- Modify: `server/app/routers/pipeline.py`
- Test: `server/tests/test_agency_console.py`

- [ ] **Step 1: Write the failing pipeline summary test**

Append to `server/tests/test_agency_console.py`:

```python
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.orm import sessionmaker

from app.db_models import PipelineRun
from app.services.video_agency_team import build_video_agency_team


@pytest.mark.asyncio
async def test_pipeline_layers_store_transparency_summaries(db, test_db, monkeypatch):
    from app.routers import pipeline

    TestSession = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    monkeypatch.setattr(pipeline, "SessionLocal", TestSession)

    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "agency_team": build_video_agency_team(),
                "visual_style": {"prompt": "cyber-noir"},
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        status="pending",
        storyboard_json={
            "frames": [{
                "narration": "Lin enters.",
                "image_prompt": "Lin in cyber-noir clinic.",
                "duration": 5,
                "audio_mode": "tts",
                "reference_urls": ["https://cdn.test/ref.png"],
            }]
        },
    )
    db.add(episode)
    db.flush()
    run = PipelineRun(series_id=series.id, episode_id=episode.id, mode="fully_automatic", status="running")
    db.add(run)
    db.commit()

    async def fake_pixelle_request(method, path, db=None, **kwargs):
        if path == "/api/image/generate":
            return {"images": ["https://cdn.test/generated.png"]}
        if path == "/api/content/narration":
            return {"narration": "Lin enters."}
        if path == "/api/content/title":
            return {"title": "Pilot"}
        if path == "/api/content/image-prompt":
            return {"image_prompt": "Lin in cyber-noir clinic."}
        if path == "/api/video/generate/async":
            return {"task_id": "task-1"}
        if path == "/api/video/task/task-1":
            return {"status": "completed", "progress": 100, "video_path": "frame.mp4", "duration": 5}
        if path == "/api/postproduction/execute":
            return {"video_path": "final.mp4", "duration": 5}
        raise AssertionError(path)

    monkeypatch.setattr(pipeline, "_pixelle_request", fake_pixelle_request)
    monkeypatch.setattr(pipeline.asyncio, "sleep", AsyncMock())

    await pipeline._run_all_layers(run.id)

    db.expire_all()
    saved = db.query(PipelineRun).filter(PipelineRun.id == run.id).one()
    layer_4 = saved.layers_json["4"]
    assert layer_4["agency_roles"]
    assert layer_4["quality_gates"]
    assert layer_4["input_summary"]["frame_count"] == 1
    assert layer_4["input_summary"]["reference_count"] == 1
    assert layer_4["output_summary"]["video_path"] == "frame.mp4"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py::test_pipeline_layers_store_transparency_summaries -q
```

Expected: FAIL because layer entries do not yet include summary fields.

- [ ] **Step 3: Add summary helpers to pipeline**

In `server/app/routers/pipeline.py`, add:

```python
def _count_refs(frames: list[dict]) -> int:
    return sum(len(frame.get("reference_urls") or []) for frame in frames)


def _quality_gates_for_layer(common: dict, layer_index: int) -> list[str]:
    phase = "final_edit" if layer_index == 5 else "render" if layer_index in (0, 3, 4) else "storyboard"
    return ((common.get("agency_context") or {}).get("quality_gates") or {}).get(phase, [])


def _agency_roles_for_layer(common: dict, layer_index: int) -> list[str]:
    roles = (common.get("agency_context") or {}).get("core_roles") or []
    if layer_index in (0, 3, 4):
        return [role for role in roles if role in ("ai_engineer", "prompt_engineer", "short_video_editing_coach")]
    if layer_index == 5:
        return [role for role in roles if role in ("short_video_editing_coach", "douyin_strategist", "software_architect")]
    return [role for role in roles if role in ("short_video_editing_coach", "douyin_strategist", "prompt_engineer")]


def _layer_input_summary(common: dict) -> dict:
    frames = common.get("frames") or []
    return {
        "frame_count": len(frames),
        "reference_count": _count_refs(frames),
        "style_lock_version": (common.get("style_constraints") or {}).get("style_lock_version", 0),
        "has_storyboard": bool(frames),
        "target_duration": common.get("target_duration", 0),
    }


def _layer_output_summary(result: dict) -> dict:
    frames = result.get("frames") or []
    summary = {
        "frame_result_count": len(frames),
        "image_count": len(result.get("images") or result.get("image_urls") or []),
        "status": result.get("status", ""),
    }
    video_path = result.get("video_path") or result.get("video_url")
    if video_path:
        summary["video_path"] = video_path
    if result.get("duration") is not None:
        summary["duration"] = result.get("duration")
    if frames:
        last_video = next((f.get("video_path") or f.get("video_url") for f in reversed(frames) if f.get("video_path") or f.get("video_url")), "")
        if last_video:
            summary["video_path"] = last_video
    return summary
```

- [ ] **Step 4: Store summaries when completing each layer**

Replace the layer assignment in `_run_all_layers`:

```python
layers[str(i)] = {"status": "completed", "result": result}
```

with:

```python
layers[str(i)] = {
    "status": "completed",
    "agency_roles": _agency_roles_for_layer(common, i),
    "quality_gates": _quality_gates_for_layer(common, i),
    "input_summary": _layer_input_summary(common),
    "output_summary": _layer_output_summary(result),
    "result": result,
}
```

- [ ] **Step 5: Verify Task 2 passes**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py::test_pipeline_layers_store_transparency_summaries -q
```

Expected: `1 passed`.

## Task 3: Aggregated Console Data With Completed Run

**Files:**
- Modify: `server/tests/test_agency_console.py`
- Modify: `server/app/services/agency_console.py`

- [ ] **Step 1: Write the completed-run aggregation test**

Append:

```python
from app.db_models import GeneratedVideo


def test_agency_console_includes_latest_run_steps_and_video(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
        story_bible_json={
            "style_lock": {
                "locked": True,
                "version": 1,
                "agency_team": build_video_agency_team(),
                "missing_assets": [],
            }
        },
    )
    db.add(series)
    db.flush()
    episode = Episode(
        series_id=series.id,
        episode_number=1,
        status="done",
        video_url="final.mp4",
        storyboard_json={"frames": [{"duration": 5}], "total_duration": 5},
    )
    db.add(episode)
    db.flush()
    run = PipelineRun(
        series_id=series.id,
        episode_id=episode.id,
        status="completed",
        current_layer=5,
        layers_json={
            "5": {
                "status": "completed",
                "agency_roles": ["short_video_editing_coach"],
                "quality_gates": ["Final video is written back."],
                "input_summary": {"frame_count": 1},
                "output_summary": {"video_path": "final.mp4", "duration": 5},
                "result": {"video_path": "final.mp4", "duration": 5},
            }
        },
    )
    db.add(run)
    db.flush()
    db.add(GeneratedVideo(keyword=series.title, pixelle_task_id=run.id, video_path="final.mp4", status="completed"))
    db.commit()

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_run"]["id"] == run.id
    assert data["generated_video"]["video_path"] == "final.mp4"
    post = next(step for step in data["production_steps"] if step["id"] == "layer_5_postproduction")
    assert post["status"] == "completed"
    assert post["output_summary"]["video_path"] == "final.mp4"
```

- [ ] **Step 2: Run the test to verify it fails or exposes gaps**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py::test_agency_console_includes_latest_run_steps_and_video -q
```

Expected: pass if Task 1 service already covers completed runs, or fail on missing imports/fields. If it passes immediately, keep it as regression coverage.

- [ ] **Step 3: Fix any aggregation gaps**

If the test fails because layer fields are not copied, update the layer step construction in `build_agency_console_payload()` to prefer stored `agency_roles` and `quality_gates`:

```python
step = _step(
    step_id,
    label,
    layer.get("status") or ("running" if latest_run and latest_run.current_layer == index else "pending"),
    phase,
    team,
    input_summary=layer.get("input_summary") or {},
    output_summary=layer.get("output_summary") or {},
    persistence=["PipelineRun.layers_json"],
    error=layer.get("error") or "",
)
if layer.get("agency_roles"):
    step["agency_roles"] = layer["agency_roles"]
if layer.get("quality_gates"):
    step["quality_gates"] = layer["quality_gates"]
steps.append(step)
```

- [ ] **Step 4: Run backend agency console tests**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py -q
```

Expected: all tests in `server/tests/test_agency_console.py` pass.

## Task 4: Frontend API And Route

**Files:**
- Modify: `web/src/api/series.js`
- Modify: `web/src/router/index.js`
- Modify: `web/src/__tests__/api-clients.test.js`

- [ ] **Step 1: Write the failing API client test**

Add to the `series API` describe block in `web/src/__tests__/api-clients.test.js`:

```javascript
it('getAgencyConsole calls the agency console endpoint', async () => {
  const { getAgencyConsole } = await import('../api/series.js')
  mockGet.mockResolvedValue({ data: { ok: true } })
  await getAgencyConsole('sid')
  expect(mockGet).toHaveBeenCalledWith('/series/sid/agency-console')
})
```

- [ ] **Step 2: Run the API test to verify it fails**

Run:

```powershell
npm exec vitest -- src/__tests__/api-clients.test.js --run
```

Expected: FAIL because `getAgencyConsole` is not exported.

- [ ] **Step 3: Add the API helper**

In `web/src/api/series.js`, add:

```javascript
export function getAgencyConsole(seriesId) { return client.get(`/series/${seriesId}/agency-console`) }
```

- [ ] **Step 4: Add the route**

In `web/src/router/index.js`, add after the `series/:id` route:

```javascript
{
  path: 'series/:seriesId/agency-console',
  name: 'AgencyConsole',
  component: () => import('../views/AgencyConsolePage.vue'),
},
```

- [ ] **Step 5: Verify API tests pass**

Run:

```powershell
npm exec vitest -- src/__tests__/api-clients.test.js --run
```

Expected: all API client tests pass.

## Task 5: Agency Console Page

**Files:**
- Create: `web/src/views/AgencyConsolePage.vue`
- Create: `web/src/__tests__/agency-console-page.test.js`

- [ ] **Step 1: Write the failing page test**

Create `web/src/__tests__/agency-console-page.test.js`:

```javascript
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AgencyConsolePage from '../views/AgencyConsolePage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { seriesId: 'sid' } }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock('../api/series.js', () => ({
  getAgencyConsole: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      series: { id: 'sid', title: 'City Healer', logline: 'A doctor solves urban mysteries.' },
      style_lock: { locked: true, version: 1, missing_assets: [] },
      agency_team_status: { enabled: true, version: '2026-05-21.1', core_role_count: 5, support_role_count: 4 },
      agency_team: {
        core_roles: [{ id: 'short_video_editing_coach', name: 'Short Video Editing Coach', mission: 'Control pacing.', phase: ['storyboard', 'render', 'final_edit'] }],
        support_roles: [{ id: 'model_qa_specialist', name: 'Model QA Specialist', mission: 'Catch broken outputs.', phase: ['render', 'final_edit'] }],
        quality_gates: { render: ['Every render payload receives references.'] },
      },
      latest_run: { id: 'rid', status: 'running', current_layer: 4 },
      production_steps: [{
        id: 'layer_4_render',
        label: 'L4 视频渲染',
        status: 'running',
        phase: 'render',
        agency_roles: ['short_video_editing_coach'],
        quality_gates: ['Every render payload receives references.'],
        input_summary: { frame_count: 1, reference_count: 1 },
        output_summary: {},
        persistence: ['PipelineRun.layers_json'],
        error: '',
      }],
    },
  })),
}))

describe('AgencyConsolePage', () => {
  it('shows expert team and production transparency steps', async () => {
    const wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(wrapper.text()).toContain('专家团队透明控制台')
    expect(wrapper.text()).toContain('观察模式')
    expect(wrapper.text()).toContain('City Healer')
    expect(wrapper.text()).toContain('5 核心')
    expect(wrapper.text()).toContain('Short Video Editing Coach')
    expect(wrapper.text()).toContain('L4 视频渲染')
    expect(wrapper.text()).toContain('PipelineRun.layers_json')
  })
})
```

- [ ] **Step 2: Run the page test to verify it fails**

Run:

```powershell
npm exec vitest -- src/__tests__/agency-console-page.test.js --run
```

Expected: FAIL because `AgencyConsolePage.vue` does not exist.

- [ ] **Step 3: Create the page**

Create `web/src/views/AgencyConsolePage.vue`:

```vue
<template>
  <div class="p-6">
    <button @click="router.back()" class="text-sky-400 hover:text-sky-300 mb-4 transition cursor-pointer">&larr; 返回</button>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>

    <template v-else-if="consoleData">
      <div class="flex justify-between items-start gap-4 mb-6">
        <div>
          <h1 class="text-2xl font-bold text-slate-100">专家团队透明控制台</h1>
          <p class="text-slate-400 mt-1">{{ consoleData.series.title }}</p>
          <p class="text-xs text-slate-500 mt-2">观察模式，不打断生成流程</p>
        </div>
        <div class="text-right text-sm">
          <div :class="consoleData.style_lock.locked ? 'text-emerald-400' : 'text-amber-400'">
            {{ consoleData.style_lock.locked ? `风格已锁定 v${consoleData.style_lock.version}` : '风格未锁定' }}
          </div>
          <div class="text-cyan-300 mt-1">
            {{ consoleData.agency_team_status.core_role_count }} 核心 / {{ consoleData.agency_team_status.support_role_count }} 支援
          </div>
        </div>
      </div>

      <section class="rounded-xl border border-gray-700/50 p-4 mb-6" style="background: rgba(15, 23, 42, 0.5);">
        <h2 class="text-lg font-semibold text-slate-100 mb-3">专家团队地图</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          <div v-for="role in allRoles" :key="role.id" class="rounded-lg border border-gray-700/50 p-3" style="background: rgba(15, 23, 42, 0.45);">
            <div class="text-sm font-medium text-slate-100">{{ role.name }}</div>
            <div class="text-xs text-cyan-300 mt-1">{{ (role.phase || []).join(' / ') }}</div>
            <p class="text-xs text-slate-400 mt-2 leading-5">{{ role.mission }}</p>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-gray-700/50 p-4 mb-6" style="background: rgba(15, 23, 42, 0.5);">
        <h2 class="text-lg font-semibold text-slate-100 mb-3">生产过程时间线</h2>
        <div class="space-y-3">
          <details v-for="step in consoleData.production_steps" :key="step.id" class="rounded-lg border border-gray-700/50 p-3" style="background: rgba(15, 23, 42, 0.45);">
            <summary class="cursor-pointer flex items-center gap-3">
              <span :class="stepStatusClass(step.status)" class="px-2 py-1 rounded text-xs">{{ step.status }}</span>
              <span class="text-sm font-medium text-slate-100">{{ step.label }}</span>
              <span class="text-xs text-slate-500 ml-auto">{{ step.phase }}</span>
            </summary>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3 text-xs text-slate-400">
              <div>
                <div class="text-slate-300 mb-1">输入摘要</div>
                <pre class="whitespace-pre-wrap rounded bg-black/20 p-2">{{ formatJson(step.input_summary) }}</pre>
              </div>
              <div>
                <div class="text-slate-300 mb-1">输出摘要</div>
                <pre class="whitespace-pre-wrap rounded bg-black/20 p-2">{{ formatJson(step.output_summary) }}</pre>
              </div>
              <div>
                <div class="text-slate-300 mb-1">相关专家</div>
                <div>{{ (step.agency_roles || []).join(', ') || '-' }}</div>
              </div>
              <div>
                <div class="text-slate-300 mb-1">持久化位置</div>
                <div>{{ (step.persistence || []).join(', ') || '-' }}</div>
              </div>
              <div v-if="step.quality_gates?.length" class="lg:col-span-2">
                <div class="text-slate-300 mb-1">质量门槛</div>
                <ul class="list-disc list-inside space-y-1">
                  <li v-for="gate in step.quality_gates" :key="gate">{{ gate }}</li>
                </ul>
              </div>
              <div v-if="step.error" class="lg:col-span-2 text-red-300">{{ step.error }}</div>
            </div>
          </details>
        </div>
      </section>

      <section class="rounded-xl border border-gray-700/50 p-4" style="background: rgba(15, 23, 42, 0.5);">
        <h2 class="text-lg font-semibold text-slate-100 mb-3">质量门槛</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div v-for="(gates, phase) in consoleData.agency_team.quality_gates" :key="phase" class="rounded-lg border border-gray-700/50 p-3">
            <div class="text-sm text-cyan-300 mb-2">{{ phase }}</div>
            <ul class="text-xs text-slate-400 list-disc list-inside space-y-1">
              <li v-for="gate in gates" :key="gate">{{ gate }}</li>
            </ul>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAgencyConsole } from '../api/series.js'

const route = useRoute()
const router = useRouter()
const consoleData = ref(null)
const loading = ref(true)
const error = ref('')

const allRoles = computed(() => {
  const team = consoleData.value?.agency_team || {}
  return [...(team.core_roles || []), ...(team.support_roles || [])]
})

function formatJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function stepStatusClass(status) {
  return {
    completed: 'bg-emerald-900/40 text-emerald-400',
    running: 'bg-sky-900/40 text-sky-400',
    failed: 'bg-red-900/40 text-red-400',
    pending: 'bg-gray-800 text-slate-400',
  }[status] || 'bg-gray-800 text-slate-400'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await getAgencyConsole(route.params.seriesId)
    if (!data.ok) throw new Error('Agency console not found')
    consoleData.value = data
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
```

- [ ] **Step 4: Verify the page test passes**

Run:

```powershell
npm exec vitest -- src/__tests__/agency-console-page.test.js --run
```

Expected: `1 passed`.

## Task 6: Entry Points From Existing Pages

**Files:**
- Modify: `web/src/views/SeriesDetailPage.vue`
- Modify: `web/src/views/PipelineMonitorPage.vue`

- [ ] **Step 1: Add a series detail entry**

In `web/src/views/SeriesDetailPage.vue`, add this button next to the style lock button:

```vue
<button @click="$router.push(`/series/${series.id}/agency-console`)"
        class="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
  专家团队控制台
</button>
```

- [ ] **Step 2: Add a pipeline monitor entry**

In `web/src/views/PipelineMonitorPage.vue`, inside the top action area, add:

```vue
<button v-if="run.series_id" @click="$router.push(`/series/${run.series_id}/agency-console`)"
        class="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
  专家团队控制台
</button>
```

If the page currently only has a status badge on the right, wrap the badge and button in a `div`:

```vue
<div class="flex items-center gap-2">
  <button v-if="run.series_id" @click="$router.push(`/series/${run.series_id}/agency-console`)"
          class="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
    专家团队控制台
  </button>
  <span :class="runStatusClass(run.status)" class="px-3 py-1 rounded-lg text-sm font-medium">{{ run.status }}</span>
</div>
```

- [ ] **Step 3: Run the page tests**

Run:

```powershell
npm exec vitest -- src/__tests__/series-detail-agency.test.js src/__tests__/agency-console-page.test.js --run
```

Expected: both tests pass.

## Task 7: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
python -m pytest server/tests/test_agency_console.py server/tests/test_series_style_lock_pipeline.py server/tests/test_series_api.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run frontend focused tests**

Run:

```powershell
npm exec vitest -- src/__tests__/api-clients.test.js src/__tests__/series-detail-agency.test.js src/__tests__/agency-console-page.test.js --run
```

Expected: all selected frontend tests pass.

- [ ] **Step 3: Build frontend**

Run:

```powershell
npm run build
```

Expected: Vite build succeeds.

- [ ] **Step 4: Manual smoke check**

Run the app with the normal local dev setup, then verify:

```text
1. Open a series detail page.
2. Confirm “专家团队控制台” is visible.
3. Click it.
4. Confirm the console shows “观察模式，不打断生成流程”.
5. Confirm production steps are visible even if no run exists.
6. Start a pipeline from the original series detail button.
7. Open the console again and confirm L0-L5 statuses update from persisted run state.
```

## Self-Review

- Spec coverage: the plan covers the independent page, backend aggregation, pipeline summaries, entry points, and tests.
- Placeholder scan: no open-ended implementation steps remain.
- Type consistency: endpoint name, route name, API helper, summary field names, and Vue data shape match across tasks.
- Scope control: the plan does not add approvals, visual editing, multi-agent chat, or external publishing.
