from sqlalchemy.orm import Session

from app.db_models import ProductionSegment
from app.services.production_retry_service import retry_segment_with_impact


def retry_segment(db: Session, segment_id: str) -> ProductionSegment:
    return retry_segment_with_impact(db, segment_id)
