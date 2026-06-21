"""视频库业务域模块。

视频库业务域，负责生成视频的归档、查询和对外展示接口。本文件负责 videos_router 相关业务规则、状态转换和外部系统边界。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.models.video_library import GeneratedVideo
from app.deps import verify_admin_token, verify_ws_admin_token

router = APIRouter(prefix="/api/videos", tags=["videos"])


class VideoResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    keyword: str
    title: Optional[str] = None
    video_path: Optional[str] = None
    duration: Optional[float] = None
    status: str
    pixelle_task_id: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class VideoListResponse(BaseModel):
    items: list[VideoResponse]
    total: int


@router.get("", response_model=VideoListResponse)
def list_videos(
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    limit = min(limit, 100)
    query = db.query(GeneratedVideo)
    if keyword:
        query = query.filter(GeneratedVideo.keyword == keyword)
    if status:
        query = query.filter(GeneratedVideo.status == status)
    query = query.order_by(GeneratedVideo.created_at.desc())
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    video = db.query(GeneratedVideo).filter(GeneratedVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    return video


@router.get("/{video_id}/download")
def download_video(
    video_id: str,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    # Browser-native elements (<video>, <a>) can't set headers — accept query token as fallback
    username = None
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt
            from app.config import JWT_SECRET
            payload = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
            username = payload["sub"]
        except Exception:
            pass
    if not username and token:
        result = verify_ws_admin_token(token)
        username = result[0] if result[0] else None
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")

    video = db.query(GeneratedVideo).filter(GeneratedVideo.id == video_id).first()
    if not video or not video.video_path:
        raise HTTPException(status_code=404, detail="视频文件不存在")

    filepath = Path(video.video_path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="视频文件已被删除")

    return FileResponse(str(filepath), media_type="video/mp4", filename=filepath.name)


@router.delete("/{video_id}")
def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    user = Depends(verify_admin_token),
):
    video = db.query(GeneratedVideo).filter(GeneratedVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")

    if video.video_path:
        filepath = Path(video.video_path)
        if filepath.exists():
            filepath.unlink()

    db.delete(video)
    db.commit()
    return {"deleted": True, "id": video_id}
