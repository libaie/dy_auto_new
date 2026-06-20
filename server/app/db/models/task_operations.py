"""Task operations ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_uuid)
    type = Column(String(30), nullable=False)  # nurture, search_comment, search_like, search_dm, reply_comment
    account_id = Column(String(36), ForeignKey("accounts.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    params = Column(JSON, nullable=False, default=dict)
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    result = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    chain_instance_id = Column(String(36), ForeignKey("chain_instances.id"), nullable=True)
    step_order = Column(Integer, nullable=True)
    lease_id = Column(String(36), nullable=True, default=None)

    account = relationship("Account", back_populates="tasks")
    device = relationship("Device", back_populates="tasks")
    chain_instance = relationship("ChainInstance", back_populates="tasks")
