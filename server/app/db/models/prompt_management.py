"""Prompt management ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String


class PromptTemplate(Base):
    """AI prompt template synchronized to devices by template ID."""

    __tablename__ = "prompt_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False, unique=True, index=True)
    industry = Column(String(50), nullable=False, default="health", index=True)
    description = Column(String(200), nullable=False, default="")
    content = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
