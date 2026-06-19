"""Chain templates and instances API."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role, verify_admin_token
from app.models import ChainInstanceCreateRequest, ChainTemplateCreate, ChainTemplateUpdate

from . import chain_use_cases, realtime_events

router = APIRouter(prefix="/api/chains", tags=["chains"])


@router.post("/templates")
async def create_template(
    request: ChainTemplateCreate,
    db: Session = Depends(get_db),
    user = Depends(require_role("admin")),
):
    user_id, _ = user
    try:
        template = chain_use_cases.create_template(db, request, user_id)
    except chain_use_cases.StepOrderError as error:
        raise HTTPException(status_code=422, detail=str(error))
    await realtime_events.broadcast_chains_changed()
    return template


@router.get("/templates")
def list_templates(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return chain_use_cases.list_templates(db, skip, limit, user)


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        return chain_use_cases.get_template(db, template_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="模板不存在")


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    request: ChainTemplateUpdate,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        template = chain_use_cases.update_template(db, template_id, request, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="模板不存在")
    except chain_use_cases.StepOrderError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except chain_use_cases.ActiveInstancesError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_chains_changed()
    return template


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        result = chain_use_cases.delete_template(db, template_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="模板不存在")
    except chain_use_cases.ActiveInstancesError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_chains_changed()
    return result


@router.post("/instances")
async def create_instances(
    request: ChainInstanceCreateRequest,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        result = chain_use_cases.create_instances(db, request, user)
    except chain_use_cases.NoAccountsError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    await realtime_events.broadcast_chains_changed()
    return result


@router.get("/instances")
def list_instances(
    template_id: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    return chain_use_cases.list_instances(db, template_id, account_id, status, skip, limit, user)


@router.get("/instances/{instance_id}")
def get_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        return chain_use_cases.get_instance(db, instance_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="链实例不存在")


@router.post("/instances/{instance_id}/cancel")
async def cancel_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        result, notifications = chain_use_cases.cancel_instance(db, instance_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="链实例不存在")
    except chain_use_cases.InvalidStateError as error:
        raise HTTPException(status_code=400, detail=str(error))

    for device_id, task_id in notifications:
        await realtime_events.send_cancel_task(device_id, task_id)

    await realtime_events.broadcast_chains_changed()
    return result


@router.post("/instances/{instance_id}/retry")
async def retry_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    try:
        result = chain_use_cases.retry_instance(db, instance_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="链实例不存在")
    except chain_use_cases.InvalidStateError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_chains_changed()
    return result
