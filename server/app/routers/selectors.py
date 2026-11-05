"""Selector management CRUD API — admin only."""
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File as FastAPIFile, Form
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.db_models import UISelector
from app.services.selector_validation import validate_selector_strategies
from app.deps import verify_admin_token, require_role
from app.services.selector_service import selector_service
from app.services.template_service import template_service

router = APIRouter(prefix="/api/selectors", tags=["selectors"])


class SelectorCreateRequest(BaseModel):
    action_name: str
    strategies: list[dict]
    platform_version: str = "default"
    resolution_profile: str = "default"
    description: str = ""
    category: str = ""
    purpose: str = "locate"
    strategy_logic: str = "and"
    extract_field: Optional[str] = None
    clean_mode: Optional[str] = None
    clean_pattern: Optional[str] = None
    clean_prompt: Optional[str] = None


class SelectorUpdateRequest(BaseModel):
    strategies: Optional[list[dict]] = None
    platform_version: Optional[str] = None
    resolution_profile: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    purpose: Optional[str] = None
    strategy_logic: Optional[str] = None
    extract_field: Optional[str] = None
    clean_mode: Optional[str] = None
    clean_pattern: Optional[str] = None
    clean_prompt: Optional[str] = None
    # Note: version is auto-bumped on any change, not user-settable


class SelectorToggleRequest(BaseModel):
    enabled: bool


@router.get("")
def list_selectors(
    include_disabled: bool = Query(False),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    selectors = selector_service.list_all_selectors(db, include_disabled=include_disabled, category=category)
    version = selector_service.get_version(db)
    return {"selectors": selectors, "total": len(selectors), "version": version}


# --- Template image endpoints (must precede /{action_name} to avoid route shadowing) ---

@router.get("/templates")
def list_templates(
    resolution: str = Query(None),
    user = Depends(verify_admin_token),
):
    templates = template_service.list_templates(resolution=resolution)
    return {"templates": templates, "total": len(templates)}


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = FastAPIFile(...),
    action_name: str = Form(""),
    resolution: str = Query("default"),
    user = Depends(require_role("admin")),
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
    template_service.save_template(filename, content, resolution=resolution)
    return {"filename": filename, "size": len(content), "resolution": resolution}


@router.delete("/templates/{filename}")
def delete_template(
    filename: str,
    resolution: str = Query("default"),
    user = Depends(require_role("admin")),
):
    deleted = template_service.delete_template(filename, resolution=resolution)
    if not deleted:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return {"deleted": True, "filename": filename}


@router.get("/{action_name}")
def get_selector(
    action_name: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    sel = selector_service.get_selector(db, action_name)
    if not sel:
        raise HTTPException(status_code=404, detail="Selector not found")
    return sel


@router.post("")
async def create_selector(
    request: SelectorCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        validate_selector_strategies(request.strategies, request.purpose)
        sel = selector_service.create_selector(
            db, action_name=request.action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
            resolution_profile=request.resolution_profile,
            description=request.description,
            category=request.category,
            purpose=request.purpose,
            strategy_logic=request.strategy_logic,
            extract_field=request.extract_field,
            clean_mode=request.clean_mode,
            clean_pattern=request.clean_pattern,
            clean_prompt=request.clean_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_invalidation("selectors_changed")
    return sel


@router.put("/{action_name}")
async def update_selector(
    action_name: str,
    request: SelectorUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        # Resolve the same composite key as update_selector, including disabled records.
        query = db.query(UISelector).filter(UISelector.action_name == action_name)
        if request.platform_version:
            query = query.filter(UISelector.platform_version == request.platform_version)
        if request.resolution_profile:
            query = query.filter(UISelector.resolution_profile == request.resolution_profile)
        existing = query.first()
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Selector '{action_name}' not found")
        validate_selector_strategies(
            request.strategies if request.strategies is not None else existing.strategies,
            request.purpose if request.purpose is not None else (existing.purpose or 'locate'),
        )
        sel = selector_service.update_selector(
            db, action_name=action_name,
            strategies=request.strategies,
            platform_version=request.platform_version,
            resolution_profile=request.resolution_profile,
            description=request.description,
            category=request.category,
            purpose=request.purpose,
            strategy_logic=request.strategy_logic,
            extract_field=request.extract_field,
            clean_mode=request.clean_mode,
            clean_pattern=request.clean_pattern,
            clean_prompt=request.clean_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_invalidation("selectors_changed")
    return sel


@router.delete("/{action_name}")
async def delete_selector(
    action_name: str,
    platform_version: Optional[str] = Query(None),
    resolution_profile: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    deleted = selector_service.delete_selector(db, action_name,
        platform_version=platform_version, resolution_profile=resolution_profile)
    if not deleted:
        raise HTTPException(status_code=404, detail="Selector not found")

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_invalidation("selectors_changed")
    return {"deleted": True, "action_name": action_name}


@router.patch("/{action_name}/toggle")
async def toggle_selector(
    action_name: str,
    request: SelectorToggleRequest,
    platform_version: Optional[str] = Query(None),
    resolution_profile: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    try:
        sel = selector_service.toggle_selector(db, action_name, request.enabled,
            platform_version=platform_version, resolution_profile=resolution_profile)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_invalidation("selectors_changed")
    return sel
