import pytest
from pydantic import ValidationError

from app.services.agency_creative_patch_contracts import (
    CreativePatchProposal,
    CreativePatchStatus,
    normalize_patch_payload,
)


def test_storyboard_patch_accepts_only_allowed_after_fields():
    proposal = CreativePatchProposal.model_validate({
        "patch_type": "storyboard_patch",
        "target_type": "storyboard_frame",
        "target_id": "shot-001",
        "stage": "storyboard",
        "title": "强化前三秒钩子",
        "reason": "原分镜缺少可见冲突。",
        "before": {"image_prompt": "原画面", "unsafe": "kept only as before snapshot"},
        "after": {
            "image_prompt": "主角在会议室被当众羞辱，纸张飞散",
            "video_prompt": "纸张砸向镜头后快速推近主角表情",
            "unexpected_column": "blocked",
        },
        "apply_policy": "requires_human_approval",
        "priority": "high",
    })

    normalized = normalize_patch_payload(proposal)

    assert normalized.after == {
        "image_prompt": "主角在会议室被当众羞辱，纸张飞散",
        "video_prompt": "纸张砸向镜头后快速推近主角表情",
    }
    assert normalized.status == CreativePatchStatus.PROPOSED


def test_patch_after_must_have_executable_allowed_field():
    proposal = CreativePatchProposal.model_validate({
        "patch_type": "image_prompt_patch",
        "target_type": "production_segment",
        "target_id": "segment-001",
        "stage": "image_stage",
        "title": "空改稿",
        "reason": "专家必须给出可执行改稿。",
        "before": {"image_prompt": "原图"},
        "after": {"unknown_field": "should be rejected"},
        "apply_policy": "requires_human_approval",
    })

    with pytest.raises(ValueError, match="executable"):
        normalize_patch_payload(proposal)


def test_unknown_patch_type_is_rejected():
    with pytest.raises(ValidationError):
        CreativePatchProposal.model_validate({
            "patch_type": "shell_command_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "storyboard",
            "title": "非法补丁",
            "reason": "不能执行命令。",
            "before": {},
            "after": {},
            "apply_policy": "requires_human_approval",
        })


def test_patch_target_type_must_match_patch_type():
    with pytest.raises(ValidationError):
        CreativePatchProposal.model_validate({
            "patch_type": "image_prompt_patch",
            "target_type": "storyboard_frame",
            "target_id": "shot-001",
            "stage": "image_stage",
            "title": "错误目标",
            "reason": "图像提示词补丁必须绑定生产片段。",
            "before": {},
            "after": {"image_prompt": "新提示词"},
            "apply_policy": "requires_human_approval",
        })
