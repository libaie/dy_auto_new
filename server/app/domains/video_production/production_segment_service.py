from sqlalchemy.orm import Session

from app.db.models.video_production import ProductionSegment
from app.domains.video_production.production_retry_service import retry_segment_with_impact


def retry_segment(db: Session, segment_id: str) -> ProductionSegment:
    return retry_segment_with_impact(db, segment_id)
