"""流水线编排 API — 模型感知 dispatch + L4 同步轮询 + Seedance 路由."""
import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.deps import verify_admin_token, require_role
from app.db_models import PipelineRun, AIModel
from app.services.crypto import decrypt
from app.services.pixelle_client import _pixelle_request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

BJT = timezone(timedelta(hours=8))

# ============================================================
# Layer definitions
# ============================================================

LAYER_DEFS = [
    {"index": 0, "label": "assets",          "model_key": "imageModel", "desc": "图像生成"},
    {"index": 1, "label": "story_narration", "model_key": "scriptLLM",  "desc": "故事旁白"},
    {"index": 2, "label": "story_title",     "model_key": "scriptLLM",  "desc": "故事标题"},
    {"index": 3, "label": "director",        "model_key": "scriptLLM",  "desc": "图像提示词"},
    {"index": 4, "label": "render",          "model_key": "videoModel", "desc": "视频渲染"},
    {"index": 5, "label": "postproduction",  "model_key": "ttsModel",   "desc": "后处理合成"},
]

FORWARD_KEYS = {
    0: ["image_urls", "images"],
    1: ["narration", "content"],
    2: ["title", "content"],
    3: ["image_prompt"],
}

VIDEO_POLL_INTERVAL = 10
VIDEO_POLL_TIMEOUTS = {
    "seedance": 180, "kling": 120, "wan": 120, "pixelle": 120, "default": 120,
}

# ============================================================
# Pydantic schemas
# ============================================================

class PipelineStartRequest(BaseModel):
    series_id: str
    episode_id: str | None = None
    mode: str = "step_by_step"
    model_ids: dict | None = None
    director_plan: dict | None = None

# ============================================================
# Model lookup
# ============================================================

def _get_model_config(db: Session, model_id: str | None) -> dict:
    if not model_id:
        return {}
    m = db.query(AIModel).filter(AIModel.id == model_id).first()
    if not m:
        return {}
    ak = ""; asc = ""
    if m.api_key:
        try: ak = decrypt(m.api_key)
        except Exception: logger.warning("decrypt api_key failed for model %s", m.id)
    if m.api_secret:
        try: asc = decrypt(m.api_secret)
        except Exception: logger.warning("decrypt api_secret failed for model %s", m.id)
    return {
        "id": m.id, "name": m.name, "model_type": m.model_type,
        "provider": m.provider, "base_url": m.base_url or "",
        "api_key": ak, "api_secret": asc,
        "model_name": m.model_name or "",
        "config_json": m.config_json or {},
    }


def _llm_chat_completion(model: dict, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
    cfg = model.get("config_json", {})
    resp = httpx.post(
        f"{model['base_url'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {model['api_key']}"},
        json={
            "model": model["model_name"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=httpx.Timeout(120, connect=10),
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ============================================================
# Layer functions
# ============================================================

async def _layer_image_generate(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L0: Per-provider image generation routing."""
    provider = model.get("provider", "")
    base = model.get("base_url", "")

    if provider == "openai":
        cfg = model.get("config_json", {})
        resp = httpx.post(
            f"{base.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {model['api_key']}"},
            json={
                "model": model.get("model_name", "dall-e-3"),
                "prompt": common.get("image_prompt", common.get("title", "")),
                "n": 1, "size": cfg.get("default_size", "1024x1024"),
                "quality": cfg.get("default_quality", "hd"),
            },
            timeout=httpx.Timeout(120, connect=10),
        )
        resp.raise_for_status()
        data = resp.json()
        return {"provider": "openai", "images": [img["url"] for img in data.get("data", [])]}

    if provider == "seedance":
        cfg = model.get("config_json", {})
        resp = httpx.post(
            f"{base.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {model['api_key']}"},
            json={
                "model": model.get("model_name", "seedance-image"),
                "prompt": common.get("image_prompt", common.get("title", "")),
                "size": cfg.get("default_size", "1024x1024"),
            },
            timeout=httpx.Timeout(120, connect=10),
        )
        resp.raise_for_status()
        data = resp.json()
        return {"provider": "seedance", "images": [img["url"] for img in data.get("data", [])]}

    # Fallback: Pixelle-Video
    result = await _pixelle_request("POST", "/api/image/generate", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_narration(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L1: LLM narration or Pixelle-Video fallback."""
    if model.get("api_key") and model.get("base_url"):
        cfg = model.get("config_json", {})
        messages = [
            {"role": "system", "content": "你是一个短视频编剧，为视频画面生成简洁生动的旁白文案。只输出旁白文案。"},
            {"role": "user", "content": f"为以下内容生成旁白：{common.get('title', '')} {common.get('context', '')}"},
        ]
        text = _llm_chat_completion(model, messages,
                                     temperature=cfg.get("temperature", 0.7),
                                     max_tokens=cfg.get("max_tokens", 4096))
        return {"provider": model["provider"], "narration": text}
    result = await _pixelle_request("POST", "/api/content/narration", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_title(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L2: LLM title or Pixelle-Video fallback."""
    if model.get("api_key") and model.get("base_url"):
        cfg = model.get("config_json", {})
        messages = [
            {"role": "system", "content": "你是一个短视频编剧，为视频系列生成吸引人的标题。只输出标题。"},
            {"role": "user", "content": f"为以下内容生成标题：{common.get('context', common.get('title', ''))}"},
        ]
        title = _llm_chat_completion(model, messages,
                                      temperature=cfg.get("temperature", 0.8),
                                      max_tokens=min(cfg.get("max_tokens", 4096), 200))
        return {"provider": model["provider"], "title": title.strip()}
    result = await _pixelle_request("GET", "/api/content/title", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_image_prompt(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L3: LLM image prompts or Pixelle-Video fallback."""
    if model.get("api_key") and model.get("base_url"):
        cfg = model.get("config_json", {})
        narration = common.get("narration", common.get("title", ""))
        messages = [
            {"role": "system", "content": "你是一个AI图像提示词专家。为给定的旁白生成高质量的图像生成提示词，描述画面构图、光线、风格。只输出提示词。"},
            {"role": "user", "content": f"旁白：{narration}"},
        ]
        prompt = _llm_chat_completion(model, messages,
                                       temperature=cfg.get("temperature", 0.7),
                                       max_tokens=min(cfg.get("max_tokens", 4096), 500))
        return {"provider": model["provider"], "image_prompt": prompt.strip()}
    result = await _pixelle_request("POST", "/api/content/image-prompt", db, json=common)
    return {"provider": "pixelle", **result}


async def _layer_video_generate(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L4: Video generation with sync polling (ADR-0003) + Seedance routing (ADR-0002)."""
    provider = model.get("provider", "pixelle")
    if provider == "seedance":
        return await _video_seedance_generate(run, model, common)
    return await _video_pixelle_poll(run, common, db)


async def _video_pixelle_poll(run: PipelineRun, common: dict, db: Session) -> dict:
    """Pixelle-Video submit + poll (ADR-0003)."""
    submit = await _pixelle_request("POST", "/api/video/generate/async", db, json=common)
    task_id = submit.get("task_id") or submit.get("id", "")
    if not task_id:
        return {"provider": "pixelle", "status": "submitted", **submit}

    max_polls = VIDEO_POLL_TIMEOUTS["pixelle"]
    for attempt in range(max_polls):
        await asyncio.sleep(VIDEO_POLL_INTERVAL)
        try:
            status_resp = await _pixelle_request("GET", f"/api/video/task/{task_id}", db)
        except Exception as e:
            logger.warning("L4 poll %d/%d failed: %s", attempt + 1, max_polls, e)
            if attempt >= 2: raise RuntimeError(f"视频任务轮询连续失败: {e}")
            continue

        status_val = status_resp.get("status", "")
        layers = run.layers_json or {}
        layers["4"] = {"status": "running", "progress": status_resp.get("progress", 0),
                        "task_id": task_id, "provider": "pixelle"}
        run.layers_json = layers; db.commit()

        if status_val in ("completed", "succeeded", "done"):
            return {"provider": "pixelle", "status": "completed", "task_id": task_id, **status_resp}
        if status_val in ("failed", "error"):
            raise RuntimeError(f"视频生成失败: {status_resp.get('error', status_val)}")

    raise RuntimeError(f"视频生成超时 ({max_polls * VIDEO_POLL_INTERVAL}s)")


async def _video_seedance_generate(run: PipelineRun, model: dict, common: dict) -> dict:
    """Seedance submit + poll (ADR-0002 + ADR-0003)."""
    base_url = model.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
    model_name = model.get("model_name", "doubao-seedance-2-0-260128")
    cfg = model.get("config_json", {})

    content = [{"type": "text", "text": common.get("image_prompt", common.get("title", ""))}]
    for url in common.get("image_urls", []):
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": model_name,
        "content": content,
        "parameters": {
            "aspect_ratio": cfg.get("default_aspect_ratio", "9:16"),
            "duration": cfg.get("default_duration", 5),
            "resolution": cfg.get("default_resolution", "720p"),
        },
    }

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {model['api_key']}"},
        timeout=httpx.Timeout(600, connect=10),
    ) as client:
        submit_resp = await client.post("/contents/generations/tasks", json=payload)
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        task_id = submit_data.get("id") or submit_data.get("task_id")
        if not task_id:
            raise RuntimeError(f"Seedance submit returned no task_id: {submit_data}")

        max_polls = VIDEO_POLL_TIMEOUTS["seedance"]
        for attempt in range(max_polls):
            await asyncio.sleep(VIDEO_POLL_INTERVAL)
            try:
                poll_resp = await client.get(f"/contents/generations/tasks/{task_id}")
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
            except Exception as e:
                logger.warning("Seedance poll %d/%d failed: %s", attempt + 1, max_polls, e)
                if attempt >= 2: raise RuntimeError(f"Seedance 轮询连续失败: {e}")
                continue

            status_val = poll_data.get("status", "unknown")
            layers = run.layers_json or {}
            layers["4"] = {"status": "running", "progress": poll_data.get("progress", 0),
                            "task_id": task_id, "provider": "seedance"}
            run.layers_json = layers; db.commit()

            if status_val == "succeeded":
                videos = poll_data.get("output", {}).get("videos", [])
                video_url = videos[0].get("url", "") if videos else ""
                return {"provider": "seedance", "status": "completed", "task_id": task_id, "video_url": video_url}
            if status_val == "failed":
                err = poll_data.get("error", {}).get("message", "任务失败")
                raise RuntimeError(f"Seedance 视频生成失败: {err}")

        raise RuntimeError(f"Seedance 视频生成超时 ({max_polls * VIDEO_POLL_INTERVAL}s)")


async def _layer_postproduction(run: PipelineRun, model: dict, common: dict, db: Session) -> dict:
    """L5: Post-production compositing."""
    result = await _pixelle_request("POST", "/api/postproduction/execute", db, json=common)
    return {"provider": "pixelle", **result}


_LAYER_FNS = [
    _layer_image_generate, _layer_narration, _layer_title,
    _layer_image_prompt, _layer_video_generate, _layer_postproduction,
]

# ============================================================
# Pipeline endpoints
# ============================================================

@router.post("/start")
async def pipeline_start(
    body: PipelineStartRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    existing = db.query(PipelineRun).filter(
        PipelineRun.series_id == body.series_id,
        PipelineRun.status.in_(["pending", "running"]),
    ).first()
    if existing:
        raise HTTPException(409, f"Series {body.series_id} 已有运行中的流水线 (run_id={existing.id})")

    run = PipelineRun(
        series_id=body.series_id,
        episode_id=body.episode_id,
        mode=body.mode,
        model_ids=body.model_ids or {},
        status="running",
        started_at=datetime.now(BJT),
    )
    db.add(run); db.commit(); db.refresh(run)
    run_id = run.id

    task = asyncio.create_task(_run_all_layers(run_id, body.director_plan))
    task.add_done_callback(
        lambda t: logger.error("Pipeline task failed: %s", t.exception()) if t.exception() else None
    )
    return {"ok": True, "run_id": run_id}


async def _run_all_layers(run_id: str, director_plan: dict | None = None):
    local_db = SessionLocal()
    run = None
    try:
        run = local_db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            return

        model_ids = run.model_ids or {}
        common = {"series_id": run.series_id, "episode_id": run.episode_id or ""}

        frames = []
        if director_plan:
            frames = director_plan.get("frames", [])
            if frames:
                common["frame_count"] = len(frames)

        # Hydrate common from already-completed layers (resume support)
        prev_layers = (run.layers_json or {}).items()
        for _li_str, _lr in prev_layers:
            _li = int(_li_str)
            if _lr.get("status") != "completed":
                continue
            _res = _lr.get("result", {}) or {}
            for key in FORWARD_KEYS.get(_li, []):
                val = _res.get(key)
                if val:
                    common[key] = val
                    if key == "images":
                        common.setdefault("image_urls", val)

        for layer_def in LAYER_DEFS:
            i = layer_def["index"]
            layers = run.layers_json or {}
            if layers.get(str(i), {}).get("status") == "completed":
                continue

            run.current_layer = i
            local_db.commit()

            model_key = layer_def["model_key"]
            model_id = model_ids.get(model_key)
            model_config = _get_model_config(local_db, model_id)

            layer_fn = _LAYER_FNS[i]

            if frames and i in (0, 3, 4):
                frame_results = []
                for fi, frame in enumerate(frames):
                    frame_common = {**common, **frame, "frame_index": fi}
                    frame_results.append(await layer_fn(run, model_config, frame_common, local_db))
                result = {"frames": frame_results}
            else:
                result = await layer_fn(run, model_config, common, local_db)
                # Forward layer output to subsequent layers via common
                for key in FORWARD_KEYS.get(i, []):
                    val = result.get(key)
                    if val:
                        common[key] = val
                        # Normalize image keys so consumers (Seedance) find them
                        if key == "images":
                            common.setdefault("image_urls", val)

            layers[str(i)] = {"status": "completed", "result": result}
            run.layers_json = layers
            local_db.commit()

        run.status = "completed"
        run.completed_at = datetime.now(BJT)
    except Exception as e:
        tb = traceback.format_exc()
        if run is not None:
            logger.error("Pipeline %s failed at layer %d: %s\n%s",
                         run_id, run.current_layer if run else -1, e, tb)
            run.status = "failed"
            run.error_log = f"{e}\n{tb}"
        else:
            logger.error("Pipeline _run_all_layers failed before run loaded: %s\n%s", e, tb)
    finally:
        local_db.commit()
        local_db.close()


@router.post("/resume/{run_id}")
async def pipeline_resume(run_id: str, db: Session = Depends(get_db),
                          _ = Depends(require_role("admin"))):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run or run.status not in ("pending", "running", "paused"):
        raise HTTPException(400, "PipelineRun not resumable")
    run.status = "running"; db.commit()
    task = asyncio.create_task(_run_all_layers(run_id))
    task.add_done_callback(
        lambda t: logger.error("Pipeline resume failed: %s", t.exception()) if t.exception() else None
    )
    return {"ok": True, "run_id": run.id}


@router.get("/runs/{series_id}")
def list_runs(series_id: str, db: Session = Depends(get_db),
              _ = Depends(verify_admin_token)):
    runs = db.query(PipelineRun).filter(
        PipelineRun.series_id == series_id
    ).order_by(PipelineRun.created_at.desc()).all()
    return {"ok": True, "runs": [
        {col.name: getattr(r, col.name) for col in PipelineRun.__table__.columns}
        for r in runs
    ]}


@router.get("/runs/{series_id}/{run_id}")
def get_run(series_id: str, run_id: str, db: Session = Depends(get_db),
            _ = Depends(verify_admin_token)):
    run = db.query(PipelineRun).filter(
        PipelineRun.id == run_id, PipelineRun.series_id == series_id
    ).first()
    if not run:
        raise HTTPException(404, "PipelineRun not found")
    return {"ok": True, "run": {
        col.name: getattr(run, col.name) for col in PipelineRun.__table__.columns
    }}
