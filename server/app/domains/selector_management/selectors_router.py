"""选择器管理业务域模块。

选择器管理业务域，负责 UI 选择器模板、版本和设备端匹配配置。本文件负责 selectors_router 相关业务规则、状态转换和外部系统边界。
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File as FastAPIFile, Form
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.deps import verify_admin_token, require_role
from app.domains.selector_management.selector_service import selector_service
from app.domains.selector_management.template_service import template_service

router = APIRouter(prefix="/api/selectors", tags=["selectors"])


class SelectorCreateRequest(BaseModel):
    """业务类：承载 SelectorCreateRequest 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 SelectorUpdateRequest 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 SelectorToggleRequest 相关的数据结构、状态或业务协作。"""
    enabled: bool


@router.get("")
def list_selectors(
    include_disabled: bool = Query(False),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_selectors 对应的业务流程、校验或数据转换。"""
    selectors = selector_service.list_all_selectors(db, include_disabled=include_disabled, category=category)
    version = selector_service.get_version(db)
    return {"selectors": selectors, "total": len(selectors), "version": version}


# --- Template image endpoints (must precede /{action_name} to avoid route shadowing) ---

@router.get("/templates")
def list_templates(
    resolution: str = Query(None),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_templates 对应的业务流程、校验或数据转换。"""
    templates = template_service.list_templates(resolution=resolution)
    return {"templates": templates, "total": len(templates)}


@router.post("/templates/upload")
async def upload_template(
    file: UploadFile = FastAPIFile(...),
    action_name: str = Form(""),
    resolution: str = Query("default"),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 upload_template 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 delete_template 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 get_selector 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 create_selector 对应的业务流程、校验或数据转换。"""
    try:
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
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return sel


@router.put("/{action_name}")
async def update_selector(
    action_name: str,
    request: SelectorUpdateRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 update_selector 对应的业务流程、校验或数据转换。"""
    try:
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
        raise HTTPException(status_code=404, detail=str(e))

    version = selector_service.get_version(db)
    from app.ws_manager import pair_ws_manager
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return sel


@router.delete("/{action_name}")
async def delete_selector(
    action_name: str,
    platform_version: Optional[str] = Query(None),
    resolution_profile: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    """业务函数：处理 delete_selector 对应的业务流程、校验或数据转换。"""
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
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
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
    """业务函数：处理 toggle_selector 对应的业务流程、校验或数据转换。"""
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
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})
    return sel
