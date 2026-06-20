"""Creative library ORM models."""

from app.config import bj_now
from app.db.base import Base, _uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship


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


class Character(Base):
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    role_type = Column(String(20), nullable=False, default="protagonist")
    gender = Column(String(10), nullable=False, default="male")
    age_range = Column(String(20), nullable=True)
    personality = Column(Text, nullable=True)
    appearance_desc = Column(Text, nullable=True)
    outfit_desc = Column(Text, nullable=True)
    avatar_front_url = Column(Text, nullable=True)
    avatar_side_url = Column(Text, nullable=True)
    avatar_threequarter_url = Column(Text, nullable=True)
    avatar_fullbody_url = Column(Text, nullable=True)
    default_voice_id = Column(String(100), nullable=True)
    meta_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    anchors = relationship("CharacterAnchor", back_populates="character", cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    scene_type = Column(String(20), nullable=False, default="indoor")
    location_desc = Column(Text, nullable=True)
    lighting = Column(String(50), nullable=True)
    mood = Column(String(50), nullable=True)
    reference_wideshot_url = Column(Text, nullable=True)
    reference_midshot_url = Column(Text, nullable=True)
    reference_aerial_url = Column(Text, nullable=True)
    meta_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())
    anchors = relationship("SceneAnchor", back_populates="scene", cascade="all, delete-orphan")


class CharacterAnchor(Base):
    __tablename__ = "character_anchors"
    __table_args__ = (
        UniqueConstraint("character_id", "reference_slot", name="uq_character_anchor_slot"),
        Index("idx_character_anchors_character_id", "character_id"),
        Index("idx_character_anchors_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    character_id = Column(String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, default="")
    reference_slot = Column(String(80), nullable=False, default="avatar_front_url")
    base_prompt = Column(Text, nullable=False, default="")
    anchor_image_url = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    ref_mode = Column(String(80), nullable=False, default="character_face")
    provider_options_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="draft")
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    character = relationship("Character", back_populates="anchors")


class SceneAnchor(Base):
    __tablename__ = "scene_anchors"
    __table_args__ = (
        UniqueConstraint("scene_id", "reference_slot", name="uq_scene_anchor_slot"),
        Index("idx_scene_anchors_scene_id", "scene_id"),
        Index("idx_scene_anchors_status", "status"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    scene_name = Column(String(100), nullable=False, default="")
    reference_slot = Column(String(80), nullable=False, default="reference_wideshot_url")
    environment_prompt = Column(Text, nullable=False, default="")
    anchor_image_url = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    ref_mode = Column(String(80), nullable=False, default="scene_environment")
    provider_options_json = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), nullable=False, default="draft")
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, nullable=False, default=lambda: bj_now())
    updated_at = Column(DateTime, nullable=False, default=lambda: bj_now(), onupdate=lambda: bj_now())

    scene = relationship("Scene", back_populates="anchors")
