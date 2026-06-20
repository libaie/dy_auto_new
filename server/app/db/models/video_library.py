"""Video library ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship


class GeneratedVideo(Base):
    """Generated short video row."""
    __tablename__ = "generated_videos"

    id = Column(String(36), primary_key=True, default=_uuid)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=True)
    keyword = Column(String(200), nullable=False)
    title = Column(String(500), nullable=True)
    video_path = Column(String(500), nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    pixelle_task_id = Column(String(100), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    task = relationship("Task")
