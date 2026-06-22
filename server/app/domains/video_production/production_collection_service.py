"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_collection_service 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.video_production import VideoCollection
from app.db.models import Episode, Series


def create_collection_from_approved_episodes(db: Session, series_id: str) -> VideoCollection:
    """业务函数：处理 create_collection_from_approved_episodes 对应的业务流程、校验或数据转换。

    入参：db、series_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    series = db.query(Series).filter(Series.id == series_id).first()
    if not series:
        raise ValueError("Series not found")

    episodes = (
        db.query(Episode)
        .filter(
            Episode.series_id == series_id,
            Episode.status == "done",
            Episode.video_url.isnot(None),
            func.trim(Episode.video_url) != "",
        )
        .order_by(Episode.episode_number.asc(), Episode.id.asc())
        .all()
    )
    if not episodes:
        raise ValueError("没有可打包剧集：请先完成至少一集并生成视频。")
    collection = VideoCollection(
        series_id=series_id,
        status="draft",
        included_episode_ids=[episode.id for episode in episodes],
        duration_seconds=sum(float(episode.duration_seconds or 0) for episode in episodes),
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection
