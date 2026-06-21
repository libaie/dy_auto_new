"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_creative_patch_contracts 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class CreativePatchType(StrEnum):
    """业务类：承载 CreativePatchType 相关的数据结构、状态或业务协作。"""
    SCRIPT = "script_patch"
    STORYBOARD = "storyboard_patch"
    IMAGE_PROMPT = "image_prompt_patch"
    VIDEO_PROMPT = "video_prompt_patch"
    EDIT_MANIFEST = "edit_manifest_patch"


class CreativePatchTargetType(StrEnum):
    """业务类：承载 CreativePatchTargetType 相关的数据结构、状态或业务协作。"""
    EPISODE_SCRIPT = "episode_script"
    STORYBOARD_FRAME = "storyboard_frame"
    PRODUCTION_SEGMENT = "production_segment"
    EDIT_MANIFEST = "edit_manifest"


class CreativePatchStatus(StrEnum):
    """业务类：承载 CreativePatchStatus 相关的数据结构、状态或业务协作。"""
    PROPOSED = "proposed"
    EDITED = "edited"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


class CreativePatchPriority(StrEnum):
    """业务类：承载 CreativePatchPriority 相关的数据结构、状态或业务协作。"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


ALLOWED_AFTER_FIELDS: dict[CreativePatchType, set[str]] = {
    CreativePatchType.SCRIPT: {"hook", "beats", "scene_outlines", "visual_shots", "notes"},
    CreativePatchType.STORYBOARD: {
        "image_prompt",
        "video_prompt",
        "narration",
        "duration",
        "action",
        "emotion",
        "shot_type",
        "continuity_notes",
        "reference_urls",
    },
    CreativePatchType.IMAGE_PROMPT: {"image_prompt", "negative_prompt", "reference_instructions"},
    CreativePatchType.VIDEO_PROMPT: {"video_prompt", "duration", "continuity_notes", "expected_end_state"},
    CreativePatchType.EDIT_MANIFEST: {
        "subtitle_style",
        "bgm_policy",
        "intro_outro",
        "watermark",
        "output_spec",
        "rhythm_notes",
    },
}

TARGETS_BY_PATCH_TYPE: dict[CreativePatchType, set[CreativePatchTargetType]] = {
    CreativePatchType.SCRIPT: {CreativePatchTargetType.EPISODE_SCRIPT},
    CreativePatchType.STORYBOARD: {CreativePatchTargetType.STORYBOARD_FRAME},
    CreativePatchType.IMAGE_PROMPT: {CreativePatchTargetType.PRODUCTION_SEGMENT},
    CreativePatchType.VIDEO_PROMPT: {CreativePatchTargetType.PRODUCTION_SEGMENT},
    CreativePatchType.EDIT_MANIFEST: {CreativePatchTargetType.EDIT_MANIFEST},
}


class CreativePatchProposal(BaseModel):
    """业务类：承载 CreativePatchProposal 相关的数据结构、状态或业务协作。"""
    patch_type: CreativePatchType
    target_type: CreativePatchTargetType
    target_id: str
    stage: str
    title: str
    reason: str
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    apply_policy: str = "requires_human_approval"
    priority: CreativePatchPriority = CreativePatchPriority.NORMAL
    status: CreativePatchStatus = CreativePatchStatus.PROPOSED

    @field_validator("target_id", "stage", "title", "reason")
    @classmethod
    def non_empty(cls, value: str) -> str:
        """业务函数：处理 non_empty 对应的业务流程、校验或数据转换。"""
        text = str(value or "").strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("apply_policy")
    @classmethod
    def requires_human_approval(cls, value: str) -> str:
        """业务函数：处理 requires_human_approval 对应的业务流程、校验或数据转换。"""
        if value != "requires_human_approval":
            raise ValueError("creative patches require human approval")
        return value

    @model_validator(mode="after")
    def validate_target_matches_patch(self) -> "CreativePatchProposal":
        """业务函数：处理 validate_target_matches_patch 对应的业务流程、校验或数据转换。"""
        if self.target_type not in TARGETS_BY_PATCH_TYPE[self.patch_type]:
            raise ValueError("target_type does not match patch_type")
        return self


def normalize_patch_payload(proposal: CreativePatchProposal) -> CreativePatchProposal:
    """业务函数：处理 normalize_patch_payload 对应的业务流程、校验或数据转换。"""
    allowed = ALLOWED_AFTER_FIELDS[proposal.patch_type]
    normalized_after = {key: value for key, value in proposal.after.items() if key in allowed}
    if not normalized_after:
        raise ValueError("creative patch after must include at least one executable allowed field")
    return proposal.model_copy(update={
        "after": normalized_after,
        "status": CreativePatchStatus.PROPOSED,
    })
