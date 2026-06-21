"""Seedance 集成业务域模块。

Seedance 集成业务域，负责视频生成 provider 的提交、查询和代理边界。本文件负责 seedance_router 相关业务规则、状态转换和外部系统边界。
"""

import asyncio
import logging
import os

import httpx
from langchain_core.tools import tool
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role

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

_client: httpx.AsyncClient | None = None
_client_key: str | None = None


def _get_api_key(db: Session | None) -> str:
    """业务函数：处理 _get_api_key 对应的业务流程、校验或数据转换。"""
    key = os.getenv("SEEDANCE_API_KEY", "")
    if db is not None:
        try:
            from app.db.models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "seedance_api_key").first()
            if row and row.value:
                key = str(row.value)
        except Exception:
            logger.warning("Failed to resolve Seedance API key from DB", exc_info=True)
    if not key:
        raise HTTPException(status_code=400, detail="请先在系统设置中配置 Seedance API Key")
    return key


def _get_client(api_key: str) -> httpx.AsyncClient:
    """业务函数：处理 _get_client 对应的业务流程、校验或数据转换。"""
    global _client, _client_key
    if _client is None or _client_key != api_key or getattr(_client, "is_closed", False):
        if _client and not _client.is_closed:
            try:
                asyncio.ensure_future(_client.aclose())
            except Exception:
                pass
        # Seedance provider 调用集中使用受控客户端，避免各路由自行处理鉴权和超时。
        _client = httpx.AsyncClient(
            trust_env=False,
            base_url=SEEDANCE_API_URL,
            timeout=httpx.Timeout(600, connect=10),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        _client_key = api_key
    return _client


api_router = APIRouter(prefix="/api/seedance", tags=["seedance"])


class SeedanceGenerateRequest(BaseModel):
    """业务类：承载 SeedanceGenerateRequest 相关的数据结构、状态或业务协作。"""
    prompt: str = Field(..., min_length=1, max_length=2000)
    aspect_ratio: str = "9:16"
    duration: int = Field(5, ge=1, le=15)
    resolution: str = "720p"
    image_urls: list[str] = Field(default_factory=list)


@tool
async def submit_seedance_generation(
    api_key: str,
    prompt: str,
    aspect_ratio: str,
    duration: int,
    resolution: str,
    image_urls: list[str],
) -> dict:
    """业务函数：处理 submit_seedance_generation 对应的业务流程、校验或数据转换。"""
    """Submit one Seedance video generation task through the provider API."""
    content = [{"type": "text", "text": prompt}]
    for url in image_urls:
        clean = str(url).strip()
        if clean:
            content.append({"type": "image_url", "image_url": {"url": clean}})
    payload = {
        "model": SEEDANCE_MODEL_ID,
        "content": content,
        "parameters": {
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "resolution": resolution,
        },
    }
    resp = await _get_client(api_key).post("/contents/generations/tasks", json=payload)
    data = resp.json()
    if resp.is_success:
        return {"ok": True, "task_id": data.get("id") or data.get("task_id")}
    return {"ok": False, "error": data.get("error", {}).get("message", str(data))}


@tool
async def query_seedance_task(api_key: str, task_id: str) -> dict:
    """业务函数：处理 query_seedance_task 对应的业务流程、校验或数据转换。"""
    """Query one Seedance video generation task through the provider API."""
    resp = await _get_client(api_key).get(f"/contents/generations/tasks/{task_id}")
    data = resp.json()
    if not resp.is_success:
        return {"ok": False, "error": data.get("error", {}).get("message", "查询失败")}

    status = data.get("status", "unknown")
    result = {"ok": True, "task_id": task_id, "status": status}
    if status == "succeeded":
        videos = (data.get("output") or {}).get("videos", [])
        if videos:
            result["video_url"] = videos[0].get("url", "")
        result["progress"] = 100
    elif status == "failed":
        result["error"] = data.get("error", {}).get("message", "任务失败")
    else:
        result["progress"] = data.get("progress", 0)
    return result


@api_router.post("/generate")
async def seedance_generate(
    body: SeedanceGenerateRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 seedance_generate 对应的业务流程、校验或数据转换。"""
    """Submit a Seedance video generation task."""
    del user
    try:
        return await submit_seedance_generation.ainvoke({
            "api_key": _get_api_key(db),
            "prompt": body.prompt,
            "aspect_ratio": body.aspect_ratio,
            "duration": body.duration,
            "resolution": body.resolution,
            "image_urls": body.image_urls,
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Seedance generate failed")
        raise HTTPException(status_code=502, detail=f"Seedance 任务提交失败: {exc}") from exc


@api_router.get("/task/{task_id}")
async def seedance_get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 seedance_get_task 对应的业务流程、校验或数据转换。"""
    """Query a Seedance video generation task."""
    del user
    try:
        return await query_seedance_task.ainvoke({"api_key": _get_api_key(db), "task_id": task_id})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Seedance task query failed")
        raise HTTPException(status_code=502, detail=f"Seedance 任务查询失败: {exc}") from exc


proxy_router = APIRouter(prefix="/api/seedance-proxy", tags=["seedance-proxy"])
PROXY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


async def _do_proxy(request: Request, db: Session, path: str = "") -> Response:
    """业务函数：处理 _do_proxy 对应的业务流程、校验或数据转换。"""
    api_key = _get_api_key(db)
    client = _get_client(api_key)

    target_path = path.lstrip("/")
    if request.query_params:
        target_path += "?" + str(request.query_params)

    forward_headers = {}
    for key, value in request.headers.items():
        if key.lower() not in _STRIP_REQ_HEADERS:
            forward_headers[key] = value

    body = await request.body()
    try:
        # Seedance provider 调用集中使用受控客户端，避免各路由自行处理鉴权和超时。
        resp = await client.request(
            method=request.method,
            url=target_path,
            headers=forward_headers,
            content=body or None,
        )
        proxy_headers = {}
        for key, value in resp.headers.items():
            if key.lower() not in _STRIP_RES_HEADERS:
                proxy_headers[key] = value
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
    except httpx.RequestError as exc:
        logger.warning("Seedance proxy failed: %s", exc)
        raise HTTPException(status_code=502, detail="Seedance API 代理请求失败") from exc
    except Exception as exc:
        logger.exception("Unexpected Seedance proxy error")
        raise HTTPException(status_code=502, detail="代理服务异常") from exc


@proxy_router.api_route("/{path:path}", methods=PROXY_METHODS)
async def proxy_seedance(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 proxy_seedance 对应的业务流程、校验或数据转换。"""
    del user
    return await _do_proxy(request, db, path)


@proxy_router.api_route("/", methods=PROXY_METHODS)
async def proxy_seedance_root(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 proxy_seedance_root 对应的业务流程、校验或数据转换。"""
    del user
    return await _do_proxy(request, db, "")
