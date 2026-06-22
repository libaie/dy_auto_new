"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_segment_service 相关业务规则、状态转换和外部系统边界。
"""

from sqlalchemy.orm import Session

from app.db.models.video_production import ProductionSegment
from app.domains.video_production.production_retry_service import retry_segment_with_impact


def retry_segment(db: Session, segment_id: str) -> ProductionSegment:
    """业务函数：处理 retry_segment 对应的业务流程、校验或数据转换。

    入参：db、segment_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return retry_segment_with_impact(db, segment_id)
