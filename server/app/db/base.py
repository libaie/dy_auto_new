"""Shared SQLAlchemy declarative base."""

import uuid

from sqlalchemy.orm import DeclarativeBase


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass
