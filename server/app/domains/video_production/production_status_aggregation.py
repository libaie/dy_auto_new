"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_status_aggregation 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy.orm import Session

from app.db.models.video_production import ProductionEpisode, ProductionPlan, ProductionScene, ProductionSegment, ProductionShot


def _parent_status(child_statuses: list[str]) -> str:
    if not child_statuses:
        return "planned"
    if any(status in {"failed_terminal"} for status in child_statuses):
        return "failed_terminal"
    if any(status in {"failed", "failed_retryable"} for status in child_statuses):
        return "failed_retryable"
    if any(status in {"image_running", "video_running", "composing"} for status in child_statuses):
        return "running"
    if any(status in {"image_review_pending", "video_review_pending", "blocked_by_review"} for status in child_statuses):
        return "blocked_by_review"
    if all(status == "completed" for status in child_statuses):
        return "completed"
    if all(status == "paused" for status in child_statuses):
        return "paused"
    return "running"


def recompute_from_segment(db: Session, segment_id: str) -> None:
    segment = db.query(ProductionSegment).filter(ProductionSegment.id == segment_id).first()
    if not segment:
        return

    shot = db.query(ProductionShot).filter(ProductionShot.id == segment.shot_plan_id).one()
    shot.status = _parent_status([
        row.status
        for row in db.query(ProductionSegment).filter(ProductionSegment.shot_plan_id == shot.id).all()
    ])

    scene = db.query(ProductionScene).filter(ProductionScene.id == shot.scene_plan_id).one()
    scene.status = _parent_status([
        row.status
        for row in db.query(ProductionShot).filter(ProductionShot.scene_plan_id == scene.id).all()
    ])

    episode = db.query(ProductionEpisode).filter(ProductionEpisode.id == scene.episode_plan_id).one()
    episode.status = _parent_status([
        row.status
        for row in db.query(ProductionScene).filter(ProductionScene.episode_plan_id == episode.id).all()
    ])

    plan = db.query(ProductionPlan).filter(ProductionPlan.id == episode.plan_id).one()
    plan.status = _parent_status([
        row.status
        for row in db.query(ProductionEpisode).filter(ProductionEpisode.plan_id == plan.id).all()
    ])

    db.commit()
