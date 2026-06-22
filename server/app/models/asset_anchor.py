"""素材锚点模型。

定义创意素材锚点的数据结构，支撑素材库和生产引用。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


MAX_PROVIDER_SEED = 2147483647


class AnchorStatus(str, Enum):
    """业务类：承载 AnchorStatus 相关的数据结构、状态或业务协作。

    类参数：DRAFT、FAILED、GENERATING、LOCKED 承载该类的业务配置、状态或数据字段。
    """
    DRAFT = "draft"
    GENERATING = "generating"
    LOCKED = "locked"
    FAILED = "failed"


class AnchorReferenceMode(str, Enum):
    """业务类：承载 AnchorReferenceMode 相关的数据结构、状态或业务协作。

    类参数：CHARACTER_FACE、CHARACTER_FULL_BODY、CONTROLNET_FACE、IMAGE_TO_IMAGE、SCENE_ENVIRONMENT 承载该类的业务配置、状态或数据字段。
    """
    CONTROLNET_FACE = "controlnet_face"
    IMAGE_TO_IMAGE = "image_to_image"
    CHARACTER_FACE = "character_face"
    CHARACTER_FULL_BODY = "character_fullbody"
    SCENE_ENVIRONMENT = "scene_environment"


class CharacterAnchor(BaseModel):
    """业务类：承载 CharacterAnchor 相关的数据结构、状态或业务协作。

    类参数：anchor_image_url、base_prompt、character_id、id、metadata、name、provider_options、ref_mode、reference_slot、seed、status 承载该类的业务配置、状态或数据字段。
    """
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
        """业务函数：处理 validate_anchor_image_url 对应的业务流程、校验或数据转换。

        入参：value 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        return _validate_optional_image_url(value)


class SceneAnchor(BaseModel):
    """业务类：承载 SceneAnchor 相关的数据结构、状态或业务协作。

    类参数：anchor_image_url、environment_prompt、id、metadata、provider_options、ref_mode、reference_slot、scene_id、scene_name、seed、status 承载该类的业务配置、状态或数据字段。
    """
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
        """业务函数：处理 validate_anchor_image_url 对应的业务流程、校验或数据转换。

        入参：value 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        return _validate_optional_image_url(value)


class AnchorReferenceImage(BaseModel):
    """业务类：承载 AnchorReferenceImage 相关的数据结构、状态或业务协作。

    类参数：anchor_id、asset_id、asset_type、name、priority、provider、ref_image_url、ref_mode、role、slot、url 承载该类的业务配置、状态或数据字段。
    """
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
        """业务函数：处理 validate_url 对应的业务流程、校验或数据转换。

        入参：value 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("url is required")
        return clean


class AnchorProviderPayload(BaseModel):
    """业务类：承载 AnchorProviderPayload 相关的数据结构、状态或业务协作。

    类参数：provider_options、ref_image_url、ref_mode、reference_images、seed 承载该类的业务配置、状态或数据字段。
    """
    reference_images: list[dict[str, Any]] = Field(default_factory=list)
    provider_options: dict[str, Any] = Field(default_factory=dict)
    ref_image_url: str | None = None
    ref_mode: str | None = None
    seed: int | None = Field(default=None, ge=0, le=MAX_PROVIDER_SEED)


class ComposedShotPrompt(BaseModel):
    """业务类：承载 ComposedShotPrompt 相关的数据结构、状态或业务协作。

    类参数：input_image_url、prompt、provider_options、reference_images、reference_urls、seed、shot_id 承载该类的业务配置、状态或数据字段。
    """
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
        """业务函数：处理 validate_input_image_url 对应的业务流程、校验或数据转换。

        入参：value 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        return _validate_optional_image_url(value)


def _validate_optional_image_url(value: str | None) -> str | None:
    """业务函数：处理 _validate_optional_image_url 对应的业务流程、校验或数据转换。

    入参：value 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    clean = str(value or "").strip()
    if not clean:
        return None
    if clean.lower().startswith(("http://", "https://", "data:image/")):
        return clean
    raise ValueError("image URL must be http(s) or data:image")
