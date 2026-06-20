"""Content collection ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, Text


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="comment")
    body = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(String(36), primary_key=True, default=_uuid)
    word = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class RepliedComment(Base):
    """Comment reply dedupe row."""
    __tablename__ = "replied_comments"

    content_hash = Column(String(64), primary_key=True)
    author = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    replied_by_device = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())


class DMSequence(Base):
    """DM sequence template."""
    __tablename__ = "dm_sequences"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    messages = Column(JSON, nullable=False)
    variants = Column(JSON, nullable=True)
    industry = Column(String(50), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
