from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional

from app.config import DEVICE_SECRET
from app.models import TaskResultReport, PollResponse
from app.services.task_service import task_service
from app.services.selector_service import SelectorService

router = APIRouter(prefix="/api/device", tags=["device"])

selector_service = SelectorService()


def _verify_device_secret(x_device_secret: Optional[str] = Header(None)):
    if x_device_secret != DEVICE_SECRET:
        raise HTTPException(status_code=401, detail="Invalid device secret")


@router.get("/poll", response_model=PollResponse)
def poll_tasks(
    device_id: str = Query(...),
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)

    task = task_service.get_pending_task(device_id)
    version = selector_service.get_version()

    return PollResponse(
        task=task,
        selectors_version=version,
    )


@router.post("/report")
def report_result(
    report: TaskResultReport,
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)

    task = task_service.report_result(
        task_id=report.task_id,
        status=report.status,
        result=report.result,
        ui_snapshot=report.ui_snapshot,
    )
    return task


@router.post("/heartbeat")
def heartbeat(
    device_id: str = Query(...),
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)
    return {"status": "ok", "device_id": device_id}


@router.get("/selectors")
def get_selectors(
    version: int = Query(0),
    x_device_secret: Optional[str] = Header(None, alias="X-Device-Secret"),
):
    _verify_device_secret(x_device_secret)

    current_version, selectors = selector_service.get_all_selectors()
    if version == current_version:
        return {"version": current_version, "selectors": None, "changed": False}

    return {
        "version": current_version,
        "selectors": selectors,
        "changed": True,
    }
