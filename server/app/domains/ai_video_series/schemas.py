"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 schemas 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from pydantic import BaseModel, Field


class SeriesCreate(BaseModel):
    title: str
    logline: Optional[str] = None
    genre: str = "drama"
    total_episodes: int = 30
    target_duration: int = 90
    mode: str = "step_by_step"
    pilot_first: bool = True


class SeriesUpdate(BaseModel):
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    total_episodes: Optional[int] = None
    target_duration: Optional[int] = None
    mode: Optional[str] = None
    pilot_first: Optional[bool] = None


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None


class StyleLockResponse(BaseModel):
    ok: bool
    status: Optional[str] = None
    story_bible: dict = Field(default_factory=dict)
    missing_assets: list[dict] = Field(default_factory=list)
    audit_reports: list[dict] = Field(default_factory=list)


class StyleLockWorkerStepRequest(BaseModel):
    lease_id: str = "style-lock-worker"
    batch_size: int = Field(default=1, ge=1, le=20)


class StoryPlanWorkerStepRequest(BaseModel):
    lease_id: str = "story-plan-worker"
    batch_size: int = Field(default=1, ge=1, le=20)


class EpisodeScriptGenerationRequest(BaseModel):
    target_duration_seconds: int | None = Field(default=None, ge=1)
