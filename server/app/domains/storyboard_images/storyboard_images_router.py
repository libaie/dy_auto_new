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
    return user[0] if isinstance(user, tuple) else None


class StoryboardImageTaskRequest(BaseModel):
    series_id: str
    run_id: str | None = None
    force: bool = False
    count: int = Field(1, ge=1, le=15)
    size: str | None = None


class PromoteStoryboardImageRequest(BaseModel):
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
    return list_storyboard_image_state(db, series_id=series_id, episode_id=episode_id, run_id=run_id)


@router.post("/assets/{asset_id}/promote")
def promote_asset(
    asset_id: str,
    body: PromoteStoryboardImageRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    return promote_storyboard_image_asset(
        db,
        asset_id=asset_id,
        run_id=body.run_id,
        frame_id=body.frame_id,
        episode_id=body.episode_id,
        asset_version=body.asset_version,
        user_id=_auth_user_id(user),
    )
