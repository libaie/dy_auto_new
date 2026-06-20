"""Model configuration ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, UniqueConstraint


class AIModel(Base):
    """AI model connection parameters per provider/model type."""

    __tablename__ = "ai_models"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    model_type = Column(String(20), nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    base_url = Column(String(300), nullable=True)
    api_key = Column(String(500), nullable=True)
    api_secret = Column(String(500), nullable=True)
    model_name = Column(String(100), nullable=True)
    config_json = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("model_type", "provider", "model_name", name="uq_ai_models_type_provider_name"),
    )
