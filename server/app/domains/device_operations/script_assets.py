"""Device script assets, selector sync, templates, and calibration routes."""
import io

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File as FastAPIFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token, verify_device_secret
from app.domains.prompt_management.prompt_template_service import prompt_template_service
from app.domains.selector_management.selector_service import selector_service
from app.ws_manager import pair_ws_manager

router = APIRouter()
template_router = APIRouter()


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):

    current_version, selectors = selector_service.get_all_selectors(db, device_id=device_id)
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }


@router.get("/prompt-templates")
def get_prompt_templates(
    version: int = Query(0),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    current_version, templates = prompt_template_service.get_all_templates(db)
    if version == current_version:
        return {"version": current_version, "templates": None, "changed": False}

    return {
        "version": current_version,
        "templates": templates,
        "changed": True,
    }


@router.get("/script-version")
def script_version(
    _: None = Depends(verify_device_secret),
):
    from app.domains.device_operations.script_service import script_service
    return {"version": script_service.get_version()}


@router.get("/script-download")
def script_download(
    _: None = Depends(verify_device_secret),
):
    from app.domains.device_operations.script_service import script_service
    from fastapi.responses import Response
    data = script_service.download_script()
    if data is None:
        raise HTTPException(status_code=404, detail="No script available")
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=device-script.zip"},
    )


@router.post("/script-upload")
async def script_upload(
    file: UploadFile = FastAPIFile(...),
    user = Depends(verify_admin_token),
):
    from app.domains.device_operations.script_service import script_service
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    new_version = script_service.upload_script(io.BytesIO(content))
    return {"version": new_version, "size": len(content)}


@template_router.get("/templates")
def device_list_templates(
    device_id: str = Depends(verify_device_secret),
    db: Session = Depends(get_db),
    resolution: str = Query(None),
):
    """Return template list with MD5 hashes for incremental sync.
    Filters by device resolution profile when available."""
    from app.db.models.device_operations import Device
    from app.domains.selector_management.template_service import template_service
    if not resolution and device_id:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    templates = template_service.list_templates(resolution=resolution)
    return {"templates": templates}


@template_router.get("/templates/{filename}")
def device_download_template(
    filename: str,
    device_id: str = Depends(verify_device_secret),
    db: Session = Depends(get_db),
    resolution: str = Query(None),
):
    """Download a single template image (binary).
    Priority: explicit resolution query param > device resolution > default."""
    from app.db.models.device_operations import Device
    from app.domains.selector_management.template_service import template_service
    from fastapi.responses import FileResponse
    if not resolution:
        resolution = "default"
        if device_id:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.screen_resolution:
                resolution = device.screen_resolution
    filepath = template_service.get_template_path(filename, resolution=resolution)
    if not filepath:
        raise HTTPException(status_code=404, detail="模板文件不存在")
    return FileResponse(str(filepath), media_type="image/png", filename=filename)


class CalibrationItem(BaseModel):
    action_name: str
    filename: str
    data: str  # base64-encoded PNG


class CalibrationRequest(BaseModel):
    templates: list[CalibrationItem]
    resolution: str = ""


@template_router.post("/calibrate")
async def device_calibrate(
    request: CalibrationRequest,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device_secret),
):
    """Device uploads auto-calibrated image templates.
    Saves templates and upserts UISelector rows for this resolution profile."""
    import base64
    from app.domains.selector_management.template_service import template_service
    from app.db.models.selector_management import UISelector
    from app.db.models.device_operations import Device

    resolution = request.resolution
    if not resolution:
        device = db.query(Device).filter(Device.id == device_id).first()
        if device and device.screen_resolution:
            resolution = device.screen_resolution
    if not resolution:
        raise HTTPException(status_code=400, detail="无法确定设备分辨率")

    uploaded = 0
    for item in request.templates:
        # Decode and save template
        try:
            content = base64.b64decode(item.data)
        except Exception:
            continue
        template_service.save_template(item.filename, content, resolution=resolution)

        # Upsert selector: clone existing "default" profile selector for this resolution
        existing = db.query(UISelector).filter(
            UISelector.action_name == item.action_name,
            UISelector.resolution_profile == resolution,
        ).first()
        if not existing:
            # Clone from default profile if it exists
            default_sel = db.query(UISelector).filter(
                UISelector.action_name == item.action_name,
                UISelector.resolution_profile == "default",
            ).first()
            if default_sel:
                # Clone strategies but update image template references to the
                # newly uploaded file (original references default templates).
                import copy
                new_strategies = copy.deepcopy(default_sel.strategies)
                for st in new_strategies:
                    if st.get("type") == "image":
                        st["template"] = item.filename
                new_sel = UISelector(
                    action_name=item.action_name,
                    description=default_sel.description,
                    platform_version=default_sel.platform_version,
                    resolution_profile=resolution,
                    strategies=new_strategies,
                    version=1,
                    category=default_sel.category,
                    purpose=default_sel.purpose,
                    strategy_logic=default_sel.strategy_logic,
                    extract_field=default_sel.extract_field,
                    clean_mode=default_sel.clean_mode,
                    clean_pattern=default_sel.clean_pattern,
                    clean_prompt=default_sel.clean_prompt,
                )
                db.add(new_sel)
        uploaded += 1

    from app.domains.selector_management.selector_service import _bump_revision
    _bump_revision(db)
    db.commit()

    # Broadcast version bump
    version = selector_service.get_version(db)
    await pair_ws_manager.broadcast_to_devices({
        "event": "selectors_updated",
        "version": version,
    })
    await pair_ws_manager.broadcast_to_admins({"event": "selectors_changed"})

    return {"uploaded": uploaded, "resolution": resolution}
