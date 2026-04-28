"""Device-facing API — poll, report, heartbeat, selectors."""
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File as FastAPIFile
from typing import Optional
from sqlalchemy.orm import Session
import io

from app.models import TaskResultReport, PollResponse, DeviceRegisterRequest, RiskReport
from app.database import get_db
from app.deps import verify_device_secret
from app.services.task_service import task_service
from app.config import ANTI_DETECT_CONFIG, ANTI_DETECT_CONFIG_VERSION
from app.services.selector_service import selector_service

router = APIRouter(prefix="/api/device", tags=["device"])


@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    task = task_service.get_pending_task(db, device_id)
    version = selector_service.get_version(db)

    from app.services.device_service import device_service
    device_info = device_service.get_device_status(db, device_id)
    proxy = device_info.get("proxy_config") if device_info else None

    cancelled_task = task_service.check_cancelled_running(db, device_id)

    return PollResponse(
        task=task,
        selectors_version=version,
        proxy=proxy,
        cancelled_task_id=cancelled_task.id if cancelled_task else None,
        anti_detect_config=ANTI_DETECT_CONFIG,
        anti_detect_config_version=ANTI_DETECT_CONFIG_VERSION,
    )


@router.post("/report")
def report_result(
    report: TaskResultReport,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    try:
        task = task_service.report_result(
            db=db,
            task_id=report.task_id,
            status=report.status,
            result=report.result,
            ui_snapshot=report.ui_snapshot,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/heartbeat")
def heartbeat(
    body: dict,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    device_id = body.get("device_id", "")
    from app.services.device_service import device_service
    device_service.update_heartbeat(db, device_id)
    return {"status": "ok", "device_id": device_id}


@router.post("/register")
def register_device(
    request: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    from app.services.device_service import device_service
    return device_service.register(
        db=db, device_id=request.device_id, name=request.name,
        os_version=request.os_version, app_version=request.app_version,
    )


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):

    current_version, selectors = selector_service.get_all_selectors(db)
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }


@router.get("/script-version")
def script_version(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    return {"version": script_service.get_version()}


@router.get("/script-download")
def script_download(
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
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
    _: None = Depends(verify_device_secret),
):
    from app.services.script_service import script_service
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    new_version = script_service.upload_script(io.BytesIO(content))
    return {"version": new_version, "size": len(content)}


@router.post("/risk-report")
def report_risk(
    report: RiskReport,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_secret),
):
    """Device reports risk control detection. Marks account as risk_controlled."""
    from app.db_models import Account
    account = db.query(Account).filter(Account.id == report.account_id).first()
    if account and account.status == "active":
        account.status = "risk_controlled"
        db.commit()
    return {"status": "acknowledged", "account_status": "risk_controlled"}
