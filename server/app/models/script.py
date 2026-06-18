from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class DramaticBeatType(str, Enum):
    HOOK = "HOOK"
    CONFLICT_1 = "CONFLICT_1"
    REVERSAL = "REVERSAL"
    CLIMAX = "CLIMAX"
    CLIFFHANGER = "CLIFFHANGER"


class PipelineStage(str, Enum):
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
    beat_type: DramaticBeatType
    emotional_value: str = Field(..., min_length=1, max_length=40)
    plot_summary: str = Field(..., min_length=1, max_length=500)


class DramaticBeatList(BaseModel):
    beats: list[DramaticBeat] = Field(..., min_length=1)

    @model_validator(mode="after")
    def require_core_beats(self):
        seen = [beat.beat_type for beat in self.beats]
        missing = [beat for beat in REQUIRED_BEAT_SEQUENCE if beat not in seen]
        if missing:
            missing_names = ", ".join(beat.value for beat in missing)
            raise ValueError(f"missing required dramatic beat: {missing_names}")
        return self


class SceneOutline(BaseModel):
    scene_number: int = Field(..., ge=1)
    dramatic_beat_type: DramaticBeatType
    location: str = Field(..., min_length=1, max_length=160)
    characters: list[str] = Field(default_factory=list)
    conflict: str = Field(..., min_length=1, max_length=500)
    emotional_turn: str = Field(..., min_length=1, max_length=240)
    visual_mandate: str = Field(..., min_length=1, max_length=500)


class SceneOutlineList(BaseModel):
    scenes: list[SceneOutline] = Field(..., min_length=1)


class VisualShot(BaseModel):
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
        if not any(marker in value for marker in EMOTIONAL_TONE_MARKERS):
            raise ValueError("narration must include an emotional tone marker")
        return value


class VisualShotList(BaseModel):
    shots: list[VisualShot] = Field(..., min_length=1)


class EpisodeScript(BaseModel):
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
