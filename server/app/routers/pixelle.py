"""Pixelle-Video proxy — admin only."""
import logging
import os
from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import _resolve_pixelle_config, PIXELLE_CONFIG_PATH, JWT_SECRET
from app.database import get_db
from app.deps import verify_admin_token, verify_ws_admin_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pixelle", tags=["pixelle"])


# ---- Config bridge (Pixelle-Video config.yaml read/write) ----

class PixelleConfigUpdate(BaseModel):
    updates: dict = {}


def _read_pixelle_config() -> dict:
    path = Path(PIXELLE_CONFIG_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pixelle-Video config 文件不存在: {PIXELLE_CONFIG_PATH}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_pixelle_config(data: dict):
    path = Path(PIXELLE_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _redact_api_key(key: str) -> str:
    if not key or len(key) < 8:
        return key
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _redact_secrets(config: dict) -> dict:
    """Return a copy with API keys redacted for safe display."""
    result = config.copy()
    if "llm" in result and isinstance(result["llm"], dict):
        result["llm"] = {**result["llm"]}
        if result["llm"].get("api_key"):
            result["llm"]["api_key"] = _redact_api_key(result["llm"]["api_key"])
    if "comfyui" in result and isinstance(result["comfyui"], dict):
        result["comfyui"] = {**result["comfyui"]}
        if result["comfyui"].get("runninghub_api_key"):
            result["comfyui"]["runninghub_api_key"] = _redact_api_key(result["comfyui"]["runninghub_api_key"])
        if result["comfyui"].get("comfyui_api_key"):
            result["comfyui"]["comfyui_api_key"] = _redact_api_key(result["comfyui"]["comfyui_api_key"])
    return result


@router.get("/config")
async def get_pixelle_config(
    user = Depends(verify_admin_token),
):
    """Read Pixelle-Video config.yaml (API keys redacted)."""
    return _redact_secrets(_read_pixelle_config())


def _serialize_ai_models(db: Session) -> dict:
    """Read AIModel table and serialize to Pixelle-Video ai_models.scenes format."""
    from app.db_models import AIModel
    from app.services.crypto import decrypt

    models = db.query(AIModel).filter(AIModel.enabled == True).all()
    scenes: dict = {}
    for m in models:
        scene_key = (m.config_json or {}).get("scene_key")
        if not scene_key:
            continue
        ak = ""
        if m.api_key:
            try:
                ak = decrypt(m.api_key)
            except Exception:
                pass
        scenes[scene_key] = {
            "provider": m.provider,
            "model": m.model_name or "",
            "api_key": ak,
            "base_url": m.base_url or "",
        }
    return {"scenes": scenes}


@router.put("/config")
async def update_pixelle_config(
    body: PixelleConfigUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Update Pixelle-Video config.yaml with deep merge, then trigger reload."""
    current = _read_pixelle_config()

    def deep_merge(base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    merged = deep_merge(current, body.updates)
    merged["ai_models"] = _serialize_ai_models(db)
    _write_pixelle_config(merged)

    # Trigger Pixelle-Video to reload config from disk
    cfg = _resolve_pixelle_config(db)
    reload_ok = False
    try:
        async with httpx.AsyncClient(trust_env=False,
            base_url=cfg["url"],
            timeout=httpx.Timeout(5, connect=3),
        ) as client:
            resp = await client.post("/api/admin/reload")
            reload_ok = resp.is_success
    except Exception as e:
        logger.warning("Pixelle-Video config reload failed: %s (restart Pixelle-Video to apply)", e)

    return {"ok": True, "reloaded": reload_ok, "message": "Config saved" + (" and reloaded" if reload_ok else " — restart Pixelle-Video to apply")}


# ---- Template preview images ----
# Pixelle-Video stores preview JPGs in docs/images/ which isn't exposed via its file API.
# Serve them directly from disk to avoid modifying Pixelle-Video source.

@router.get("/template-preview/{size}/{filename}")
async def template_preview_image(
    size: str,
    filename: str,
    token: str = Query(None),
    authorization: str = Header(None),
):
    """Serve template preview image. Accepts token via query param for <img> tags."""
    username = None
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt as _jwt
            payload = _jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
            username = payload["sub"]
        except Exception:
            pass
    if not username and token:
        result = verify_ws_admin_token(token)
        username = result[0] if result[0] else None
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    preview_dir = Path(PIXELLE_CONFIG_PATH).parent / "docs" / "images" / size
    # Try exact path first, then try common extensions
    filepath = preview_dir / filename
    if not filepath.exists():
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = preview_dir / (Path(filename).stem + ext)
            if candidate.exists():
                filepath = candidate
                break
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Preview image not found: {size}/{filename}")
    suffix = filepath.suffix.lower()
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix, "image/jpeg")
    return FileResponse(str(filepath), media_type=media)


# ---- Test connection ----

@router.get("/test-connection")
async def test_connection(
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """Test connectivity to Pixelle-Video."""
    cfg = _resolve_pixelle_config(db)
    try:
        async with httpx.AsyncClient(trust_env=False,
            base_url=cfg["url"],
            timeout=httpx.Timeout(10, connect=5),
        ) as client:
            resp = await client.get("/openapi.json")
            data = resp.json()
            return {"ok": True, "version": data.get("info", {}).get("version", "unknown")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---- 透明代理 (admin) ----
# 前端 VideoStudio 页面通过此代理直接调用 Pixelle-Video 的所有 API，
# 避免浏览器 CORS 问题。代理根据 SystemSetting 中的 pixelle_video_url 转发。

PROXY_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]

# Headers to NEVER forward to downstream Pixelle-Video
_STRIP_REQUEST_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "authorization", "cookie", "x-forwarded-for", "x-forwarded-proto",
    "x-real-ip", "origin", "referer",
}

# Headers to strip from Pixelle-Video response (let FastAPI recalculate)
_STRIP_RESPONSE_HEADERS = {
    "transfer-encoding", "content-encoding", "content-length",
}

proxy_router = APIRouter(prefix="/api/pixelle-proxy", tags=["pixelle-proxy"])

# Module-level cached httpx client — reused across requests for connection pooling
_proxy_client = None
_proxy_client_url = None


def _get_proxy_client(db=None) -> httpx.AsyncClient:
    global _proxy_client, _proxy_client_url
    cfg = _resolve_pixelle_config(db)
    url = cfg["url"]
    if _proxy_client is None or _proxy_client_url != url:
        if _proxy_client:
            try:
                import asyncio
                asyncio.ensure_future(_proxy_client.aclose())
            except Exception:
                pass
        _proxy_client = httpx.AsyncClient(trust_env=False,
            base_url=url,
            timeout=httpx.Timeout(cfg["timeout"], connect=10),
        )
        _proxy_client_url = url
    return _proxy_client


async def _do_proxy(request: Request, db: Session, path: str = "") -> Response:
    """Core proxy logic — forward request to Pixelle-Video and return response."""
    client = _get_proxy_client(db)

    # Build target URL (path already handled by base_url, so strip leading /)
    target_path = path.lstrip("/")
    if request.query_params:
        target_path += "?" + str(request.query_params)

    # Forward only safe headers
    forward_headers = {}
    for key, val in request.headers.items():
        if key.lower() not in _STRIP_REQUEST_HEADERS:
            forward_headers[key] = val

    body = await request.body()

    try:
        resp = await client.request(
            method=request.method,
            url=target_path,
            headers=forward_headers,
            content=body or None,
        )

        proxy_headers = {}
        for key, val in resp.headers.items():
            if key.lower() not in _STRIP_RESPONSE_HEADERS:
                proxy_headers[key] = val

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=proxy_headers,
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Pixelle-Video 服务不可达")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Pixelle-Video 响应超时")
    except httpx.RequestError as e:
        logger.warning("Proxy request to Pixelle-Video failed: %s", e)
        raise HTTPException(status_code=502, detail="Pixelle-Video 代理请求失败")
    except Exception:
        logger.exception("Unexpected proxy error")
        raise HTTPException(status_code=502, detail="代理服务异常")


@proxy_router.api_route("/{path:path}", methods=PROXY_METHODS)
async def proxy_to_pixelle(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return await _do_proxy(request, db, path)


@proxy_router.api_route("/", methods=PROXY_METHODS)
async def proxy_root_to_pixelle(
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return await _do_proxy(request, db, "")
