"""Identity access ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, String


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), nullable=False, default="operator")
    nickname = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
