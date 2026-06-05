"""Infer visual medium constraints from story text."""
from __future__ import annotations

from typing import Any


LIVE_ACTION_KEYWORDS = (
    "现实",
    "真实",
    "真人",
    "实拍",
    "普通人",
    "普通中老年",
    "中老年",
    "生活方式",
    "日常",
    "家庭",
    "控糖",
    "血糖",
    "健康",
    "纪实",
    "documentary",
    "real life",
    "live-action",
    "photorealistic",
)

ILLUSTRATION_KEYWORDS = (
    "漫画",
    "动漫",
    "二次元",
    "插画",
    "手绘",
    "卡通",
    "anime",
    "cartoon",
    "illustration",
    "manga",
)

LIVE_ACTION_CONSTRAINT = (
    "photorealistic live-action, real human, documentary realism, natural skin texture, "
    "real-world clothing and locations, everyday Chinese life, consistent camera lens and lighting"
)

LIVE_ACTION_NEGATIVE = (
    "no anime, no cartoon, no illustration, no manga, no 3D render, no game character, "
    "no doll-like face, no stylized painting, no exaggerated fantasy costume"
)

DEFAULT_CONSTRAINT = "cinematic vertical short-video style, stable character identity, consistent lighting and color palette"
DEFAULT_NEGATIVE = "no text, no logo, no watermark"


def story_text_from_parts(*parts: Any) -> str:
    values: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            values.extend(str(value) for value in part.values() if value is not None)
        elif isinstance(part, (list, tuple)):
            values.append(story_text_from_parts(*part))
        elif part is not None:
            values.append(str(part))
    return " ".join(value.strip() for value in values if value and value.strip())


def infer_visual_style_from_story(*parts: Any) -> dict[str, str]:
    text = story_text_from_parts(*parts).lower()
    illustration_hits = [keyword for keyword in ILLUSTRATION_KEYWORDS if keyword.lower() in text]
    live_action_hits = [keyword for keyword in LIVE_ACTION_KEYWORDS if keyword.lower() in text]

    if live_action_hits and not illustration_hits:
        return {
            "medium": "photorealistic_live_action",
            "prompt": f"{LIVE_ACTION_CONSTRAINT}, no text, no logo, no watermark",
            "negative_prompt": LIVE_ACTION_NEGATIVE,
            "rationale": "故事文本包含现实/真人/日常生活信号，自动锁定为真人实拍纪实风格。",
        }

    return {
        "medium": "cinematic_default",
        "prompt": f"{DEFAULT_CONSTRAINT}, {DEFAULT_NEGATIVE}",
        "negative_prompt": DEFAULT_NEGATIVE,
        "rationale": "故事文本未明确要求真人实拍，使用默认短视频电影感风格。",
    }


def merge_visual_style(base: dict[str, Any] | None, inferred: dict[str, str]) -> dict[str, Any]:
    merged = dict(base or {})
    merged["medium"] = inferred["medium"]
    merged["prompt"] = inferred["prompt"]
    merged["negative_prompt"] = inferred["negative_prompt"]
    merged["rationale"] = inferred["rationale"]
    return merged


def append_visual_style_constraints(prompt: str, visual_style: dict[str, Any] | None) -> str:
    visual_style = visual_style or {}
    constraint = str(visual_style.get("prompt") or "").strip()
    negative = str(visual_style.get("negative_prompt") or "").strip()
    parts = [part for part in (constraint, prompt.strip(), negative) if part]
    return ". ".join(parts)


def reference_prompt_matches_visual_style(stored_prompt: str | None, visual_style: dict[str, Any] | None) -> bool:
    medium = (visual_style or {}).get("medium")
    if medium != "photorealistic_live_action":
        return True
    prompt = (stored_prompt or "").lower()
    return (
        "photorealistic live-action" in prompt
        and "real human" in prompt
        and "no anime" in prompt
        and "no cartoon" in prompt
        and "no illustration" in prompt
    )
