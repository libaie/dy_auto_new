"""素材锚点模型。

定义创意素材锚点的数据结构，支撑素材库和生产引用。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


MAX_PROVIDER_SEED = 2147483647


class AnchorStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    LOCKED = "locked"
    FAILED = "failed"


class AnchorReferenceMode(str, Enum):
    CONTROLNET_FACE = "controlnet_face"
    IMAGE_TO_IMAGE = "image_to_image"
    CHARACTER_FACE = "character_face"
    CHARACTER_FULL_BODY = "character_fullbody"
    SCENE_ENVIRONMENT = "scene_environment"


class CharacterAnchor(BaseModel):
    id: str | None = None
    character_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    reference_slot: str = Field(default="avatar_front_url", min_length=1)
    base_prompt: str = Field(..., min_length=1)
    anchor_image_url: str | None = None
    seed: int | None = Field(default=None, ge=0, le=MAX_PROVIDER_SEED)
    ref_mode: AnchorReferenceMode = AnchorReferenceMode.CHARACTER_FACE
    provider_options: dict[str, Any] = Field(default_factory=dict)
    status: AnchorStatus = AnchorStatus.DRAFT
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("anchor_image_url")
    @classmethod
    def validate_anchor_image_url(cls, value: str | None) -> str | None:
        return _validate_optional_image_url(value)


class SceneAnchor(BaseModel):
    id: str | None = None
    scene_id: str = Field(..., min_length=1)
    scene_name: str = Field(..., min_length=1)
    reference_slot: str = Field(default="reference_wideshot_url", min_length=1)
    environment_prompt: str = Field(..., min_length=1)
    anchor_image_url: str | None = None
    seed: int | None = Field(default=None, ge=0, le=MAX_PROVIDER_SEED)
    ref_mode: AnchorReferenceMode = AnchorReferenceMode.SCENE_ENVIRONMENT
    provider_options: dict[str, Any] = Field(default_factory=dict)
    status: AnchorStatus = AnchorStatus.DRAFT
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("anchor_image_url")
    @classmethod
    def validate_anchor_image_url(cls, value: str | None) -> str | None:
        return _validate_optional_image_url(value)


class AnchorReferenceImage(BaseModel):
    url: str = Field(..., min_length=1)
    ref_image_url: str = Field(..., min_length=1)
    role: Literal["character_anchor", "scene_reference"]
    asset_type: Literal["character", "scene"]
    asset_id: str = Field(..., min_length=1)
    name: str | None = None
    anchor_id: str | None = None
    slot: str = Field(..., min_length=1)
    ref_mode: AnchorReferenceMode
    provider: str = Field(..., min_length=1)
    priority: int = Field(..., ge=1)

    @field_validator("url", "ref_image_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("url is required")
        return clean


class AnchorProviderPayload(BaseModel):
    reference_images: list[dict[str, Any]] = Field(default_factory=list)
    provider_options: dict[str, Any] = Field(default_factory=dict)
    ref_image_url: str | None = None
    ref_mode: str | None = None
    seed: int | None = Field(default=None, ge=0, le=MAX_PROVIDER_SEED)


class ComposedShotPrompt(BaseModel):
    shot_id: str
    prompt: str = Field(..., min_length=1)
    seed: int | None = Field(default=None, ge=0, le=MAX_PROVIDER_SEED)
    provider_options: dict[str, Any] = Field(default_factory=dict)
    reference_images: list[dict[str, Any]] = Field(default_factory=list)
    reference_urls: list[str] = Field(default_factory=list)
    input_image_url: str | None = None

    @field_validator("input_image_url")
    @classmethod
    def validate_input_image_url(cls, value: str | None) -> str | None:
        return _validate_optional_image_url(value)


def _validate_optional_image_url(value: str | None) -> str | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    if clean.lower().startswith(("http://", "https://", "data:image/")):
        return clean
    raise ValueError("image URL must be http(s) or data:image")
