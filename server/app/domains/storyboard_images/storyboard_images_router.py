"""分镜图片业务域模块。

分镜图片业务域，负责分镜帧图片生成、绑定和状态查询。本文件负责 storyboard_images_router 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.domains.storyboard_images.storyboard_image_service import (
    create_missing_storyboard_image_tasks,
    create_storyboard_frame_image_task,
    list_storyboard_image_state,
    promote_storyboard_image_asset,
)


router = APIRouter(prefix="/api/storyboard-images", tags=["storyboard-images"])


def _auth_user_id(user) -> str | None:
    """业务函数：处理 _auth_user_id 对应的业务流程、校验或数据转换。

    入参：user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return user[0] if isinstance(user, tuple) else None


class StoryboardImageTaskRequest(BaseModel):
    """业务类：承载 StoryboardImageTaskRequest 相关的数据结构、状态或业务协作。

    类参数：count、force、run_id、series_id、size 承载该类的业务配置、状态或数据字段。
    """
    series_id: str
    run_id: str | None = None
    force: bool = False
    count: int = Field(1, ge=1, le=15)
    size: str | None = None


class PromoteStoryboardImageRequest(BaseModel):
    """业务类：承载 PromoteStoryboardImageRequest 相关的数据结构、状态或业务协作。

    类参数：asset_version、episode_id、frame_id、run_id 承载该类的业务配置、状态或数据字段。
    """
    run_id: str
    frame_id: str
    episode_id: str | None = None
    asset_version: int | None = Field(None, ge=1)


@router.post("/episodes/{episode_id}/frames/{frame_id}/tasks")
async def create_frame_task(
    episode_id: str,
    frame_id: str,
    body: StoryboardImageTaskRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 create_frame_task 对应的业务流程、校验或数据转换。

    入参：episode_id、frame_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return await create_storyboard_frame_image_task(
        db,
        series_id=body.series_id,
        episode_id=episode_id,
        frame_id=frame_id,
        run_id=body.run_id,
        force=body.force,
        count=body.count,
        size=body.size,
        user_id=_auth_user_id(user),
    )


@router.post("/episodes/{episode_id}/tasks:batch")
async def create_missing_tasks(
    episode_id: str,
    body: StoryboardImageTaskRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 create_missing_tasks 对应的业务流程、校验或数据转换。

    入参：episode_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return await create_missing_storyboard_image_tasks(
        db,
        series_id=body.series_id,
        episode_id=episode_id,
        run_id=body.run_id,
        force=body.force,
        count=body.count,
        size=body.size,
        user_id=_auth_user_id(user),
    )


@router.get("/episodes/{episode_id}")
def read_storyboard_images(
    episode_id: str,
    series_id: str = Query(...),
    run_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """业务函数：处理 read_storyboard_images 对应的业务流程、校验或数据转换。

    入参：episode_id、series_id、run_id、db、_ 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return list_storyboard_image_state(db, series_id=series_id, episode_id=episode_id, run_id=run_id)


@router.post("/assets/{asset_id}/promote")
def promote_asset(
    asset_id: str,
    body: PromoteStoryboardImageRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """业务函数：处理 promote_asset 对应的业务流程、校验或数据转换。

    入参：asset_id、body、db、user 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return promote_storyboard_image_asset(
        db,
        asset_id=asset_id,
        run_id=body.run_id,
        frame_id=body.frame_id,
        episode_id=body.episode_id,
        asset_version=body.asset_version,
        user_id=_auth_user_id(user),
    )
