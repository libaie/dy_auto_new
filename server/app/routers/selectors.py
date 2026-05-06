"""Selector management CRUD API — admin only."""
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File as FastAPIFile
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.deps import verify_admin_token
from app.services.selector_service import selector_service
from app.services.template_service import template_service

router = APIRouter(prefix="/api/selectors", tags=["selectors"])


class SelectorCreateRequest(BaseModel):
    action_name: str
    strategies: list[dict]
    platform_version: str = "default"
    description: str = ""
    category: str = ""


class SelectorUpdateRequest(BaseModel):
    strategies: Optional[list[dict]] = None
    platform_version: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    # Note: version is auto-bumped on any change, not user-settable


class SelectorToggleRequest(BaseModel):
    enabled: bool


@router.get("")
def list_selectors(
    include_disabled: bool = Query(False),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    selectors = selector_service.list_all_selectors(db, include_disabled=include_disabled, category=category)
    version = selector_service.get_version(db)
    return {"selectors": selectors, "total": len(selectors), "version": version}


@router.get("/{action_name}")
def get_selector(
    action_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    sel = selector_service.get_selector(db, action_name)
    if not sel:
        raise HTTPException(status_code=404, detail="Selector not found")
    return sel


@router.post("")
async def create_selector(
    request: SelectorCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        sel = selector_service.create_selector(
            db, action_name=request.action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
            description=request.description,
            category=request.category,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    return sel


@router.put("/{action_name}")
async def update_selector(
    action_name: str,
    request: SelectorUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        sel = selector_service.update_selector(
            db, action_name=action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
            description=request.description,
            category=request.category,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    return sel


@router.delete("/{action_name}")
async def delete_selector(
    action_name: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    deleted = selector_service.delete_selector(db, action_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Selector not found")

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    return {"deleted": True, "action_name": action_name}


@router.patch("/{action_name}/toggle")
async def toggle_selector(
    action_name: str,
    request: SelectorToggleRequest,
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_token),
):
    try:
        sel = selector_service.toggle_selector(db, action_name, request.enabled)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    return sel


# --- Template image endpoints ---

@router.get("/templates")
def list_templates(
    _: str = Depends(verify_admin_token),
):
    templates = template_service.list_templates()
    return {"templates": templates, "total": len(templates)}


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = FastAPIFile(...),
    action_name: str = "",
    _: str = Depends(verify_admin_token),
):
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="仅支持 .png/.jpg/.jpeg 格式")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    safe_name = (action_name or "template").replace("/", "_").replace("\\", "_")
    filename = f"{safe_name}_{int(time.time() * 1000)}{ext}"
    template_service.save_template(filename, content)
    return {"filename": filename, "size": len(content)}


@router.delete("/templates/{filename}")
def delete_template(
    filename: str,
    _: str = Depends(verify_admin_token),
):
    deleted = template_service.delete_template(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return {"deleted": True, "filename": filename}
