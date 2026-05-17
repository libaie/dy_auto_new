"""Seedance 2.0 集成 — 火山方舟 Ark API."""
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token

logger = logging.getLogger(__name__)

SEEDANCE_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
SEEDANCE_MODEL_ID = "doubao-seedance-2-0-260128"

_STRIP_REQ_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "authorization", "cookie", "x-forwarded-for", "x-forwarded-proto",
    "x-real-ip", "origin", "referer",
}
_STRIP_RES_HEADERS = {
    "transfer-encoding", "content-encoding", "content-length",
}

_client = None
_client_key = None


def _get_api_key(db: Session) -> str:
    key = os.getenv("SEEDANCE_API_KEY", "")
    if db:
        try:
            from app.db_models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "seedance_api_key").first()
            if row and row.value:
                key = row.value
        except Exception:
            pass
    if not key:
        raise HTTPException(status_code=400, detail="请先在系统设置中配置 Seedance API Key")
    return key


def _get_client(api_key: str) -> httpx.AsyncClient:
    global _client, _client_key
    if _client is None or _client_key != api_key:
        if _client:
            import asyncio
            try:
                asyncio.ensure_future(_client.aclose())
            except Exception:
                pass
        _client = httpx.AsyncClient(
            trust_env=False,
            base_url=SEEDANCE_API_URL,
            timeout=httpx.Timeout(600, connect=10),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        _client_key = api_key
    return _client


# ==== 便捷 API Router (/api/seedance) ====

api_router = APIRouter(prefix="/api/seedance", tags=["seedance"])


class SeedanceGenerateRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "9:16"
    duration: int = 5
    resolution: str = "720p"
    image_urls: list[str] = []


@api_router.post("/generate")
async def seedance_generate(body: SeedanceGenerateRequest, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    """提交 Seedance 视频生成任务."""
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    content = [{"type": "text", "text": body.prompt}]
    for url in body.image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    payload = {
        "model": SEEDANCE_MODEL_ID,
        "content": content,
        "parameters": {
            "aspect_ratio": body.aspect_ratio,
            "duration": body.duration,
            "resolution": body.resolution,
        },
    }

    try:
        resp = await client.post("/contents/generations/tasks", json=payload)
        data = resp.json()
        if resp.is_success:
            return {"ok": True, "task_id": data.get("id") or data.get("task_id")}
        return {"ok": False, "error": data.get("error", {}).get("message", str(data))}
    except Exception as e:
        logger.exception("Seedance generate failed")
        raise HTTPException(status_code=502, detail=f"Seedance 任务提交失败: {e}")


@api_router.get("/task/{task_id}")
async def seedance_get_task(task_id: str, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    """查询 Seedance 任务状态."""
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    try:
        resp = await client.get(f"/contents/generations/tasks/{task_id}")
        data = resp.json()
        if not resp.is_success:
            return {"ok": False, "error": data.get("error", {}).get("message", "查询失败")}

        status = data.get("status", "unknown")
        result = {"ok": True, "task_id": task_id, "status": status}

        if status == "succeeded":
            output = data.get("output", {})
            videos = output.get("videos", [])
            if videos:
                result["video_url"] = videos[0].get("url", "")
            result["progress"] = 100
        elif status == "failed":
            result["error"] = data.get("error", {}).get("message", "任务失败")
        else:
            result["progress"] = data.get("progress", 0)

        return result
    except Exception as e:
        logger.exception("Seedance task query failed")
        raise HTTPException(status_code=502, detail=f"Seedance 任务查询失败: {e}")


# ==== 透明代理 Router (/api/seedance-proxy) ====

proxy_router = APIRouter(prefix="/api/seedance-proxy", tags=["seedance-proxy"])


async def _do_proxy(request: Request, db: Session, path: str = "") -> Response:
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    target_path = path.lstrip("/")
    if request.query_params:
        target_path += "?" + str(request.query_params)

    forward_headers = {}
    for k, v in request.headers.items():
        if k.lower() not in _STRIP_REQ_HEADERS:
            forward_headers[k] = v

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=target_path,
            headers=forward_headers,
            content=body or None,
        )
        proxy_headers = {}
        for k, v in resp.headers.items():
            if k.lower() not in _STRIP_RES_HEADERS:
                proxy_headers[k] = v

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=proxy_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Seedance API 不可达")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Seedance API 响应超时")
    except httpx.RequestError as e:
        logger.warning("Seedance proxy failed: %s", e)
        raise HTTPException(status_code=502, detail="Seedance API 代理请求失败")
    except Exception:
        logger.exception("Unexpected Seedance proxy error")
        raise HTTPException(status_code=502, detail="代理服务异常")


PROXY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


@proxy_router.api_route("/{path:path}", methods=PROXY_METHODS)
async def proxy_seedance(path: str, request: Request, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    return await _do_proxy(request, db, path)


@proxy_router.api_route("/", methods=PROXY_METHODS)
async def proxy_seedance_root(request: Request, db: Session = Depends(get_db), user = Depends(verify_admin_token)):
    return await _do_proxy(request, db, "")
