from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import Episode, Series, VideoCollection


def create_collection_from_approved_episodes(db: Session, series_id: str) -> VideoCollection:
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
