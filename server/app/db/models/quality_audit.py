"""Quality audit ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Float, JSON, String, Text


class AuditReport(Base):
    __tablename__ = "audit_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    target_type = Column(String(20), nullable=False)
    target_id = Column(String(36), nullable=False)
    image_url = Column(Text, nullable=False)
    auditor_model = Column(String(50), nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    pass_fail = Column(Boolean, nullable=False, default=False)
    issues_json = Column(JSON, nullable=True, default=list)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
