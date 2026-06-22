"""Pixelle 集成业务域模块。

Pixelle 集成业务域，负责 Pixelle provider 配置、代理、阶段任务和客户端调用。本文件负责 pixelle_router 相关业务规则、状态转换和外部系统边界。
"""

import logging
import os
from pathlib import Path

import httpx
import yaml
from langchain_core.tools import tool
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import _resolve_pixelle_config, PIXELLE_CONFIG_PATH, JWT_SECRET, PIXELLE_API_KEY
from app.database import get_db
from app.deps import require_role, verify_admin_token, verify_ws_admin_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pixelle", tags=["pixelle"])


# ---- Config bridge (Pixelle-Video config.yaml read/write) ----

class PixelleConfigUpdate(BaseModel):
    """业务类：承载 PixelleConfigUpdate 相关的数据结构、状态或业务协作。

    类参数：updates 承载该类的业务配置、状态或数据字段。
    """
    updates: dict = {}


def _read_pixelle_config() -> dict:
    """业务函数：处理 _read_pixelle_config 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    path = Path(PIXELLE_CONFIG_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pixelle-Video config 文件不存在: {PIXELLE_CONFIG_PATH}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_pixelle_config(data: dict):
    """业务函数：处理 _write_pixelle_config 对应的业务流程、校验或数据转换。

    入参：data 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    path = Path(PIXELLE_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _pixelle_api_key(db: Session | None = None) -> str:
    """业务函数：处理 _pixelle_api_key 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if db is not None:
        try:
            from app.db.models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "pixelle_api_key").first()
            if row and row.value:
                return str(row.value)
        except Exception:
            logger.warning("Failed to resolve Pixelle API key from DB", exc_info=True)
    return PIXELLE_API_KEY


def _pixelle_headers(db: Session | None = None) -> dict:
    """业务函数：处理 _pixelle_headers 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Headers for direct Pixelle-Video HTTP calls (includes API key if configured)."""
    h = {}
    api_key = _pixelle_api_key(db)
    if api_key:
        h["X-API-Key"] = api_key
    return h


@tool
async def reload_pixelle_config(base_url: str, headers: dict) -> bool:
    """业务函数：处理 reload_pixelle_config 对应的业务流程、校验或数据转换。

    入参：base_url、headers 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Ask Pixelle-Video to reload its config."""
    # Pixelle 管理连接集中设置超时和鉴权头，避免各接口重复拼接 provider 配置。
    async with httpx.AsyncClient(
        trust_env=False,
        base_url=base_url,
        timeout=httpx.Timeout(5, connect=3),
        headers=headers,
    ) as client:
        # 配置 reload 是管理端受控动作，失败时只提示重启而不破坏已保存配置。
        resp = await client.post("/api/admin/reload")
        return resp.is_success


@tool
async def pixelle_openapi_probe(base_url: str, headers: dict) -> dict:
    """业务函数：处理 pixelle_openapi_probe 对应的业务流程、校验或数据转换。

    入参：base_url、headers 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Read Pixelle-Video OpenAPI metadata for a connectivity check."""
    # Pixelle 管理连接集中设置超时和鉴权头，避免各接口重复拼接 provider 配置。
    async with httpx.AsyncClient(
        trust_env=False,
        base_url=base_url,
        timeout=httpx.Timeout(10, connect=5),
        headers=headers,
    ) as client:
        resp = await client.get("/openapi.json")
        data = resp.json()
        return {"ok": True, "version": data.get("info", {}).get("version", "unknown")}


def _redact_api_key(key: str) -> str:
    """业务函数：处理 _redact_api_key 对应的业务流程、校验或数据转换。

    入参：key 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not key or len(key) < 8:
        return key
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


_SECRET_KEY_PARTS = ("api_key", "api_secret", "secret", "token", "authorization")


def _redact_secrets(config):
    """业务函数：处理 _redact_secrets 对应的业务流程、校验或数据转换。

    入参：config 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Return a deep copy with secret-looking values redacted for safe display."""
    if isinstance(config, list):
        return [_redact_secrets(item) for item in config]
    if isinstance(config, dict):
        safe = {}
        for key, value in config.items():
            if any(part in str(key).lower() for part in _SECRET_KEY_PARTS):
                safe[key] = _redact_api_key(str(value or ""))
            else:
                safe[key] = _redact_secrets(value)
        return safe
    return config


@router.get("/config")
async def get_pixelle_config(
    user = Depends(require_role("admin")),
):
    """业务函数：处理 get_pixelle_config 对应的业务流程、校验或数据转换。

    入参：user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Read Pixelle-Video config.yaml (API keys redacted)."""
    return _redact_secrets(_read_pixelle_config())


def _serialize_ai_models(db: Session) -> dict:
    """业务函数：处理 _serialize_ai_models 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Read AIModel table and serialize to Pixelle-Video ai_models.scenes format."""
    from app.db.models import AIModel
    from app.domains.system_configuration.crypto import decrypt

    models = db.query(AIModel).filter(AIModel.enabled == True).order_by(
        AIModel.sort_order.asc(),
        AIModel.created_at.asc(),
    ).all()
    scenes: dict = {}
    for m in models:
        config = m.config_json or {}
        scene_keys = config.get("scene_keys")
        if not isinstance(scene_keys, list):
            scene_keys = [config.get("scene_key")]
        scene_keys = [scene_key for scene_key in scene_keys if scene_key]
        if not scene_keys:
            continue
        ak = ""
        if m.api_key:
            try:
                ak = decrypt(m.api_key)
            except Exception:
                pass
        payload = {
            "provider": m.provider,
            "model": m.model_name or "",
            "api_key": ak,
            "base_url": m.base_url or "",
        }
        for scene_key in scene_keys:
            if scene_key in scenes:
                continue
            scenes[scene_key] = dict(payload)
    return {"scenes": scenes}


@router.put("/config")
async def update_pixelle_config(
    body: PixelleConfigUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 update_pixelle_config 对应的业务流程、校验或数据转换。

    入参：body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Update Pixelle-Video config.yaml with deep merge, then trigger reload."""
    current = _read_pixelle_config()

    def deep_merge(base, updates):
        """业务函数：处理 deep_merge 对应的业务流程、校验或数据转换。

        入参：base、updates 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
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
        reload_ok = await reload_pixelle_config.ainvoke({"base_url": cfg["url"], "headers": _pixelle_headers(db)})
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
    """业务函数：处理 template_preview_image 对应的业务流程、校验或数据转换。

    入参：size、filename、token、authorization 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Serve template preview image. Accepts token via query param for <img> tags."""
    username = None
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt as _jwt
            payload = _jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
            if payload.get("role", "admin") == "admin":
                username = payload["sub"]
        except Exception:
            pass
    if not username and token:
        result = verify_ws_admin_token(token)
        username = result[0] if result[0] and result[1] == "admin" else None
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
    user = Depends(require_role("admin")),
):
    """业务函数：处理 test_connection 对应的业务流程、校验或数据转换。

    入参：db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Test connectivity to Pixelle-Video."""
    cfg = _resolve_pixelle_config(db)
    try:
        return await pixelle_openapi_probe.ainvoke({"base_url": cfg["url"], "headers": _pixelle_headers(db)})
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
_proxy_client_api_key = None


def _get_proxy_client(db=None) -> httpx.AsyncClient:
    """业务函数：处理 _get_proxy_client 对应的业务流程、校验或数据转换。

    入参：db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    global _proxy_client, _proxy_client_url, _proxy_client_api_key
    cfg = _resolve_pixelle_config(db)
    url = cfg["url"]
    api_key = _pixelle_api_key(db)
    if _proxy_client is None or _proxy_client_url != url or _proxy_client_api_key != api_key:
        if _proxy_client:
            try:
                import asyncio
                asyncio.ensure_future(_proxy_client.aclose())
            except Exception:
                pass
        # Pixelle 管理连接集中设置超时和鉴权头，避免各接口重复拼接 provider 配置。
        _proxy_client = httpx.AsyncClient(trust_env=False,
            base_url=url,
            timeout=httpx.Timeout(cfg["timeout"], connect=10),
            headers=_pixelle_headers(db),
        )
        _proxy_client_url = url
        _proxy_client_api_key = api_key
    return _proxy_client


async def _do_proxy(request: Request, db: Session, path: str = "") -> Response:
    """业务函数：处理 _do_proxy 对应的业务流程、校验或数据转换。

    入参：request、db、path 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    api_key = _pixelle_api_key(db)
    if api_key:
        forward_headers["X-API-Key"] = api_key

    body = await request.body()

    try:
        # 透明代理只转发管理端请求，避免前端直接处理 Pixelle 凭据。
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
    user = Depends(require_role("admin")),
):
    """业务函数：处理 proxy_to_pixelle 对应的业务流程、校验或数据转换。

    入参：path、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return await _do_proxy(request, db, path)


@proxy_router.api_route("/", methods=PROXY_METHODS)
async def proxy_root_to_pixelle(
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 proxy_root_to_pixelle 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return await _do_proxy(request, db, "")
