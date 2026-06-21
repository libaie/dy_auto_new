"""内容采集业务域模块。

内容采集业务域，负责采集数据、私信序列、内容生成和实时事件。本文件负责 data_router 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_admin_token
from app.domains.content_collection import read_models


router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/comments")
def list_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_comments 对应的业务流程、校验或数据转换。"""
    return read_models.list_comments(
        db=db,
        user=user,
        keyword=keyword,
        account_id=account_id,
        search=search,
        task_id=task_id,
        skip=skip,
        limit=limit,
    )


@router.get("/users")
def list_users(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    is_private: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_users 对应的业务流程、校验或数据转换。"""
    return read_models.list_users(
        db=db,
        user=user,
        keyword=keyword,
        account_id=account_id,
        search=search,
        task_id=task_id,
        is_private=is_private,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )


@router.get("/conversations")
def list_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 list_conversations 对应的业务流程、校验或数据转换。"""
    return read_models.list_conversations(
        db=db,
        user=user,
        account_id=account_id,
        stage=stage,
        status=status,
        search=search,
        task_id=task_id,
        skip=skip,
        limit=limit,
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 get_conversation 对应的业务流程、校验或数据转换。"""
    return read_models.get_conversation(
        db=db,
        user=user,
        conversation_id=conversation_id,
    )
@router.get("/export/comments")
def export_comments(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 export_comments 对应的业务流程、校验或数据转换。"""
    return read_models.export_comments(
        db=db,
        user=user,
        keyword=keyword,
        account_id=account_id,
        search=search,
        task_id=task_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


@router.get("/export/users")
def export_users(
    keyword: Optional[str] = Query(None),
    account_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    is_private: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 export_users 对应的业务流程、校验或数据转换。"""
    return read_models.export_users(
        db=db,
        user=user,
        keyword=keyword,
        account_id=account_id,
        search=search,
        task_id=task_id,
        is_private=is_private,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )


@router.get("/export/conversations")
def export_conversations(
    account_id: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    """业务函数：处理 export_conversations 对应的业务流程、校验或数据转换。"""
    return read_models.export_conversations(
        db=db,
        user=user,
        account_id=account_id,
        stage=stage,
        status=status,
        search=search,
        task_id=task_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
