"""Device-facing API — poll, report, heartbeat, selectors."""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session

from app.models import TaskResultReport, PollResponse
from app.database import get_db
from app.deps import verify_device_secret
from app.services.task_service import task_service
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

    return PollResponse(
        task=task,
        selectors_version=version,
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
    _: None = Depends(verify_device_secret),
):
    device_id = body.get("device_id", "")
    return {"status": "ok", "device_id": device_id}


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
