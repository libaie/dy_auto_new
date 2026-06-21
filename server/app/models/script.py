"""脚本模型。

定义设备脚本和任务脚本相关的数据结构。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class DramaticBeatType(str, Enum):
    """业务类：承载 DramaticBeatType 相关的数据结构、状态或业务协作。"""
    HOOK = "HOOK"
    CONFLICT_1 = "CONFLICT_1"
    REVERSAL = "REVERSAL"
    CLIMAX = "CLIMAX"
    CLIFFHANGER = "CLIFFHANGER"


class PipelineStage(str, Enum):
    """业务类：承载 PipelineStage 相关的数据结构、状态或业务协作。"""
    DRAMATIC_BEATS = "dramatic_beats"
    SCENE_OUTLINES = "scene_outlines"
    VISUAL_SHOTS = "visual_shots"


REQUIRED_BEAT_SEQUENCE = [
    DramaticBeatType.HOOK,
    DramaticBeatType.CONFLICT_1,
    DramaticBeatType.REVERSAL,
    DramaticBeatType.CLIMAX,
    DramaticBeatType.CLIFFHANGER,
]

EMOTIONAL_TONE_MARKERS = {
    "爽",
    "憋屈",
    "震惊",
    "感动",
    "愤怒",
    "恐惧",
    "紧张",
    "崩溃",
    "委屈",
    "痛快",
    "震撼",
    "！",
    "?",
    "？",
}


class DramaticBeat(BaseModel):
    """业务类：承载 DramaticBeat 相关的数据结构、状态或业务协作。"""
    beat_type: DramaticBeatType
    emotional_value: str = Field(..., min_length=1, max_length=40)
    plot_summary: str = Field(..., min_length=1, max_length=500)


class DramaticBeatList(BaseModel):
    """业务类：承载 DramaticBeatList 相关的数据结构、状态或业务协作。"""
    beats: list[DramaticBeat] = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_core_beats(self):
        """业务函数：处理 require_core_beats 对应的业务流程、校验或数据转换。"""
        seen = [beat.beat_type for beat in self.beats]
        missing = [beat for beat in REQUIRED_BEAT_SEQUENCE if beat not in seen]
        if missing:
            missing_names = ", ".join(beat.value for beat in missing)
            raise ValueError(f"missing required dramatic beat: {missing_names}")
        return self


class SceneOutline(BaseModel):
    """业务类：承载 SceneOutline 相关的数据结构、状态或业务协作。"""
    scene_number: int = Field(..., ge=1)
    dramatic_beat_type: DramaticBeatType
    location: str = Field(..., min_length=1, max_length=160)
    characters: list[str] = Field(default_factory=list)
    conflict: str = Field(..., min_length=1, max_length=500)
    emotional_turn: str = Field(..., min_length=1, max_length=240)
    visual_mandate: str = Field(..., min_length=1, max_length=500)


class SceneOutlineList(BaseModel):
    """业务类：承载 SceneOutlineList 相关的数据结构、状态或业务协作。"""
    scenes: list[SceneOutline] = Field(..., min_length=1)


class VisualShot(BaseModel):
    """业务类：承载 VisualShot 相关的数据结构、状态或业务协作。"""
    shot_number: int = Field(..., ge=1)
    scene_number: int = Field(..., ge=1)
    beat_type: DramaticBeatType
    narration: str = Field(..., min_length=1, max_length=240)
    visual_prompt: str = Field(..., min_length=1, max_length=1200)
    video_prompt: str = Field(..., min_length=1, max_length=1200)
    duration: float = Field(..., gt=0)

    @field_validator("narration")
    @classmethod
    def narration_contains_emotional_marker(cls, value: str) -> str:
        """业务函数：处理 narration_contains_emotional_marker 对应的业务流程、校验或数据转换。"""
        if not any(marker in value for marker in EMOTIONAL_TONE_MARKERS):
            raise ValueError("narration must include an emotional tone marker")
        return value


class VisualShotList(BaseModel):
    """业务类：承载 VisualShotList 相关的数据结构、状态或业务协作。"""
    shots: list[VisualShot] = Field(..., min_length=1)


class EpisodeScript(BaseModel):
    """业务类：承载 EpisodeScript 相关的数据结构、状态或业务协作。"""
    series_id: str
    episode_id: str
    source_prompt: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    target_duration_seconds: int = Field(..., ge=1)
    episode_asset_scope: dict[str, Any] = Field(default_factory=dict)
    dramatic_beats: DramaticBeatList
    scene_outlines: SceneOutlineList
    visual_shots: VisualShotList
    agency_trace: dict[str, Any] = Field(default_factory=dict)
