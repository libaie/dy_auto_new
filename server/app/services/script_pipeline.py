from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.models.script import DramaticBeatType, PipelineStage


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "prompts" / "templates"


@dataclass(frozen=True)
class PromptPayload:
    system_prompt: str
    user_prompt: str


BEAT_CONSTRAINTS = {
    DramaticBeatType.HOOK: [
        "前3秒必须出现视觉冲突（如摔杯子、下跪、耳光或身份反差）",
        "台词字数不得超过15字",
        "语气必须极端",
    ],
    DramaticBeatType.CLIMAX: [
        "必须完成身份反转",
        "反派角色产生震惊、恐惧的视觉表现",
        "主角机位采用低角度仰拍以增强压迫感",
    ],
}

TAG_CONSTRAINTS = {
    "歪嘴战神": ["被压制的主角身份", "旁人公开轻蔑", "精准亮明权力或武力反差"],
    "都市逆袭": ["现代层级压力", "公开 stakes", "金钱或身份反差", "当场反转"],
    "主母黑化": ["家庭权力秩序", "背叛", "情绪冷转", "克制反击"],
}

TEMPLATE_NAMES = {
    PipelineStage.DRAMATIC_BEATS: "script_stage1_dramatic_beats.md",
    PipelineStage.SCENE_OUTLINES: "script_stage2_scene_outlines.md",
    PipelineStage.VISUAL_SHOTS: "script_stage3_visual_shots.md",
}


class DynamicPromptBuilder:
    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self.template_dir = template_dir

    def build(
        self,
        *,
        stage: PipelineStage,
        source_prompt: str,
        tags: list[str],
        target_duration_seconds: int,
        beat_types: list[DramaticBeatType] | None = None,
        previous_outputs: dict[str, Any] | None = None,
    ) -> PromptPayload:
        template = self._read_template(stage)
        system_prompt, user_prompt = self._split_template(template)
        rendered_user = self._render(
            user_prompt,
            source_prompt=source_prompt,
            tags="、".join(tags) if tags else "无",
            target_duration_seconds=str(target_duration_seconds),
            previous_outputs=json.dumps(previous_outputs or {}, ensure_ascii=False, sort_keys=True),
            constraints="\n".join(self._constraints(tags, beat_types or [])),
        )
        return PromptPayload(system_prompt=system_prompt.strip(), user_prompt=rendered_user.strip())

    def _read_template(self, stage: PipelineStage) -> str:
        return (self.template_dir / TEMPLATE_NAMES[stage]).read_text(encoding="utf-8")

    def _split_template(self, template: str) -> tuple[str, str]:
        system_marker = "## SYSTEM"
        user_marker = "## USER"
        if system_marker not in template or user_marker not in template:
            raise ValueError("script prompt template must contain ## SYSTEM and ## USER sections")
        system_part, user_part = template.split(user_marker, 1)
        return system_part.replace(system_marker, "", 1), user_part

    def _render(self, template: str, **values: str) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        return rendered

    def _constraints(self, tags: list[str], beat_types: list[DramaticBeatType]) -> list[str]:
        constraints: list[str] = []
        for beat_type in beat_types:
            constraints.extend(BEAT_CONSTRAINTS.get(beat_type, []))
        for tag in tags:
            constraints.extend(TAG_CONSTRAINTS.get(tag, [f"保留标签语境: {tag}"]))
        return constraints
