from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

AUTO_REPAIR_STAGE = "agency_auto_repair"
MAX_AUTO_REPAIR_ROUNDS = 2

READABILITY_FALLBACK_REASON = "专家审查结果缺少可执行结论，需要人工确认"
READABILITY_FALLBACK_EXPECTED = "由人工确认处理方式"

PAID_REPAIR_TYPES = {
    "missing_character_reference",
    "missing_scene_reference",
    "image_generation_failed",
    "image_generation_timeout",
    "video_segment_failed",
    "video_segment_timeout",
}

ALLOWED_REPAIR_TYPES = {
    "missing_character_reference",
    "missing_scene_reference",
    "storyboard_missing_references",
    "image_generation_failed",
    "image_generation_timeout",
    "video_segment_failed",
    "video_segment_timeout",
    "manual_incomplete_repair_task",
}

MOJIBAKE_TOKENS = (
    "閸", "閼", "閹", "鐟", "闂", "閻", "鐞", "閳", "娓", "锟", "�",
    "鍘", "鑰", "鎺", "瑙", "闇", "鐢", "琛", "鈥", "渆",
)


class AutoRepairPolicy(BaseModel):
    enabled: bool = False
    max_rounds: int = Field(default=MAX_AUTO_REPAIR_ROUNDS, ge=0, le=MAX_AUTO_REPAIR_ROUNDS)
    budget_limit: float = Field(default=0.0, ge=0.0)
    currency: str = "CNY"
    allowed_stages: list[str] = Field(default_factory=list)
    allowed_types: list[str] = Field(default_factory=list)
    requires_human_gate_after_repair: bool = True


class RepairTask(BaseModel):
    type: str
    stage: str
    target_type: str = "manual"
    target_id: str | None = None
    series_id: str | None = None
    auto_execute: bool = False
    requires_paid_provider: bool = False
    budget_authorized: bool = False
    priority: str = "normal"
    estimated_cost: float = Field(default=0.0, ge=0.0)
    reason: str = ""
    expected_result: str = ""
    repair_action_label: str = ""
    repair_route: str | None = None
    affected_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return value if value in ALLOWED_REPAIR_TYPES else "manual_incomplete_repair_task"

    @field_validator("reason", "expected_result", "repair_action_label")
    @classmethod
    def readable_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return text
        if looks_unreadable(text):
            return READABILITY_FALLBACK_REASON
        return text


class RepairClassificationResult(BaseModel):
    repairable: bool = False
    manual_gate_required: bool = False
    blocked_reason: str | None = None
    repair_tasks: list[RepairTask] = Field(default_factory=list)


def looks_unreadable(text: str) -> bool:
    value = str(text or "")
    if not value.strip():
        return False
    return any(token in value for token in MOJIBAKE_TOKENS)


def action_for_task(task_type: str, target_type: str, target_id: str | None) -> tuple[str, str | None]:
    if target_type == "character" and target_id:
        return "去角色资产补参考图", f"/characters/{target_id}"
    if target_type == "scene" and target_id:
        return "去场景资产补参考图", f"/scenes/{target_id}"
    if task_type == "storyboard_missing_references":
        return "去系列详情补分镜参考", None
    if task_type in {"image_generation_failed", "image_generation_timeout"}:
        return "去审查中心处理图像返修", "/ai-video-review"
    if task_type in {"video_segment_failed", "video_segment_timeout"}:
        return "去审查中心处理视频返修", "/ai-video-review"
    return "联系人工处理", None
