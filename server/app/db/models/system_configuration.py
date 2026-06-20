"""System configuration ORM models."""

from app.config import bj_now
from app.db.base import Base

from sqlalchemy import Column, DateTime, String, Text


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
