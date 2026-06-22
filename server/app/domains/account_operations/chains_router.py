"""账号运营业务域模块。

账号运营业务域，负责账号、分组、频道、链路和账号侧读写用例。本文件负责 chains_router 相关业务规则、状态转换和外部系统边界。
"""

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
    """业务函数：处理 create_template 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 list_templates 对应的业务流程、校验或数据转换。

    入参：skip、limit、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return chain_use_cases.list_templates(db, skip, limit, user)


@router.get("/templates/{template_id}")
def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_template 对应的业务流程、校验或数据转换。

    入参：template_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 update_template 对应的业务流程、校验或数据转换。

    入参：template_id、request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 delete_template 对应的业务流程、校验或数据转换。

    入参：template_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 create_instances 对应的业务流程、校验或数据转换。

    入参：request、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 list_instances 对应的业务流程、校验或数据转换。

    入参：template_id、account_id、status、skip、limit、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return chain_use_cases.list_instances(db, template_id, account_id, status, skip, limit, user)


@router.get("/instances/{instance_id}")
def get_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_instance 对应的业务流程、校验或数据转换。

    入参：instance_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 cancel_instance 对应的业务流程、校验或数据转换。

    入参：instance_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
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
    """业务函数：处理 retry_instance 对应的业务流程、校验或数据转换。

    入参：instance_id、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    try:
        result = chain_use_cases.retry_instance(db, instance_id, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="链实例不存在")
    except chain_use_cases.InvalidStateError as error:
        raise HTTPException(status_code=400, detail=str(error))
    await realtime_events.broadcast_chains_changed()
    return result
