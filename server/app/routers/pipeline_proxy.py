"""Pixelle-Video 透明代理 — 供前端 pixelle-client.js 透传调用."""
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from app.deps import verify_admin_token

router = APIRouter(prefix="/api/pixelle-proxy", tags=["pixelle-proxy"])
PIXELLE_BASE = "http://127.0.0.1:8500"
TIMEOUT = httpx.Timeout(600, connect=10)


@router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def pixelle_proxy(request: Request, path: str, _: str = Depends(verify_admin_token)):
    """透明代理所有前端 pixelle-client.js 请求到 Pixelle-Video."""
    body = None
    if request.method in ("POST", "PUT"):
        try:
            body = await request.json()
        except Exception:
            body = None

    async with httpx.AsyncClient(base_url=PIXELLE_BASE, timeout=TIMEOUT) as c:
        r = await c.request(request.method, f"/api/{path}", json=body)
        try:
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except Exception:
            return JSONResponse(content={"detail": r.text}, status_code=r.status_code)
