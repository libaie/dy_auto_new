"""Creative library ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint


class ReferenceData(Base):
    """Managed reference dictionary item."""
    __tablename__ = "reference_data"

    id = Column(String(36), primary_key=True, default=_uuid)
    category = Column(String(50), nullable=False, index=True)
    value = Column(String(100), nullable=False)
    label = Column(String(100), nullable=False)
    description = Column(String(200), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (UniqueConstraint("category", "value"),)


class ReferenceCategory(Base):
    """Managed reference dictionary category."""
    __tablename__ = "reference_categories"

    id = Column(String(36), primary_key=True, default=_uuid)
    key = Column(String(50), nullable=False, unique=True, index=True)
    label = Column(String(100), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
