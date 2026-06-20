"""Image production ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint


class ImageProductionPolicyVersion(Base):
    __tablename__ = "image_production_policy_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    policy_type = Column(String(30), nullable=False)
    name = Column(String(120), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("policy_type", "name", "version", name="uq_image_policy_version"),
        Index("idx_image_policy_versions_type_status", "policy_type", "status"),
    )


class ImageProductionStrategy(Base):
    __tablename__ = "image_production_strategies"

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    destination_role = Column(String(80), nullable=False)
    supported_modes_json = Column(JSON, nullable=False, default=list)
    default_model_id = Column(String(36), ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True)
    fallback_model_ids_json = Column(JSON, nullable=False, default=list)
    common_parameters_json = Column(JSON, nullable=False, default=dict)
    provider_options_json = Column(JSON, nullable=False, default=dict)
    review_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    cost_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    capacity_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    ab_test_policy_version_id = Column(String(36), ForeignKey("image_production_policy_versions.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("slug", name="uq_image_strategy_slug"),
        Index("idx_image_strategies_role_status", "destination_role", "status"),
        Index("idx_image_strategies_status_updated", "status", "updated_at"),
    )


class ImageProductionStrategyVersion(Base):
    __tablename__ = "image_production_strategy_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    strategy_id = Column(String(36), ForeignKey("image_production_strategies.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_image_strategy_version"),
        Index("idx_image_strategy_versions_strategy", "strategy_id"),
    )
