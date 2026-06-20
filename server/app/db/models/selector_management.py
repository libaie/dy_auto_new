"""Selector management ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text


class UISelector(Base):
    __tablename__ = "ui_selectors"

    id = Column(String(36), primary_key=True, default=_uuid)
    action_name = Column(String(100), nullable=False, index=True)
    description = Column(String(200), nullable=False, default="")
    platform_version = Column(String(50), nullable=False, default="default")
    resolution_profile = Column(String(50), nullable=False, default="default")
    strategies = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    category = Column(String(50), nullable=True, default=None, index=True)
    purpose = Column(String(20), nullable=False, default="locate")
    strategy_logic = Column(String(10), nullable=False, default="and")
    extract_field = Column(String(20), nullable=True)
    clean_mode = Column(String(20), nullable=True)
    clean_pattern = Column(Text, nullable=True)
    clean_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
