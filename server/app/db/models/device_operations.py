"""Device operations ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, Integer, String


class DevicePairRequest(Base):
    __tablename__ = "device_pair_requests"

    id = Column(String(36), primary_key=True, default=_uuid)
    pairing_token = Column(String(64), nullable=False, unique=True, index=True)
    device_id = Column(String(36), nullable=False)
    device_name = Column(String(100), nullable=False)
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(20), nullable=True)
    screen_resolution = Column(String(30), nullable=True)
    sdk_version = Column(String(20), nullable=True)
    total_memory = Column(Integer, nullable=True)
    manufacturer = Column(String(50), nullable=True)
    product = Column(String(50), nullable=True)
    device_model = Column(String(50), nullable=True)
    hardware = Column(String(50), nullable=True)
    display = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    device_secret = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
