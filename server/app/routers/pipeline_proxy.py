"""Pipeline Proxy Wrapper — 翻译层：将流水线操作映射到 Pixelle-Video 实际 API."""
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.deps import verify_admin_token

router = APIRouter(prefix="/api/pipeline-proxy", tags=["pipeline-proxy"])
PIXELLE_BASE = "http://127.0.0.1:8500/api"

TIMEOUT = httpx.Timeout(600, connect=10)


async def _pixelle_post(path: str, json: dict) -> dict:
    async with httpx.AsyncClient(base_url=PIXELLE_BASE, timeout=TIMEOUT) as c:
        r = await c.post(path, json=json)
        r.raise_for_status()
        return r.json()


async def _pixelle_get(path: str) -> dict:
    async with httpx.AsyncClient(base_url=PIXELLE_BASE, timeout=TIMEOUT) as c:
        r = await c.get(path)
        r.raise_for_status()
        return r.json()


class PipelineCommonInput(BaseModel):
    series_id: str = ""
    episode_id: str = ""


@router.post("/assets/generate")
async def assets_generate(body: PipelineCommonInput, _: str = Depends(verify_admin_token)):
    """Layer 0: 资产生成 → Pixelle image API."""
    result = await _pixelle_post("/image/generate", body.model_dump())
    return {"ok": True, "result": result}


@router.post("/story/generate")
async def story_generate(body: PipelineCommonInput, _: str = Depends(verify_admin_token)):
    """Layer 1: 故事工坊 → Pixelle content API (narration + title)."""
    narration = await _pixelle_post("/content/narration", body.model_dump())
    title = await _pixelle_post("/content/title", body.model_dump())
    return {"ok": True, "narration": narration, "title": title}


@router.post("/director/generate")
async def director_generate(body: PipelineCommonInput, _: str = Depends(verify_admin_token)):
    """Layer 2: 导演工坊 → LLM chain + image-prompt generation."""
    image_prompt = await _pixelle_post("/content/image-prompt", body.model_dump())
    return {"ok": True, "image_prompt": image_prompt}


@router.post("/render/execute")
async def render_execute(body: PipelineCommonInput, _: str = Depends(verify_admin_token)):
    """Layer 3: 渲染引擎 → Pixelle video generate async."""
    result = await _pixelle_post("/video/generate/async", body.model_dump())
    return {"ok": True, "task_id": result.get("task_id")}


@router.post("/postproduction/execute")
async def postproduction_execute(body: PipelineCommonInput, _: str = Depends(verify_admin_token)):
    """Layer 5: 后期包装 → FFmpeg 合成 (本地执行，暂留占位)."""
    return {"ok": True, "message": "Post-production executed (placeholder)"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, _: str = Depends(verify_admin_token)):
    """查询 Pixelle-Video 任务状态."""
    result = await _pixelle_get(f"/tasks/{task_id}")
    return {"ok": True, "task": result}
