"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 schemas 相关业务规则、状态转换和外部系统边界。
"""

from typing import Optional

from pydantic import BaseModel, Field


class SeriesCreate(BaseModel):
    """业务类：承载 SeriesCreate 相关的数据结构、状态或业务协作。"""
    title: str
    logline: Optional[str] = None
    genre: str = "drama"
    total_episodes: int = 30
    target_duration: int = 90
    mode: str = "step_by_step"
    pilot_first: bool = True


class SeriesUpdate(BaseModel):
    """业务类：承载 SeriesUpdate 相关的数据结构、状态或业务协作。"""
    title: Optional[str] = None
    logline: Optional[str] = None
    genre: Optional[str] = None
    total_episodes: Optional[int] = None
    target_duration: Optional[int] = None
    mode: Optional[str] = None
    pilot_first: Optional[bool] = None


class EpisodeUpdate(BaseModel):
    """业务类：承载 EpisodeUpdate 相关的数据结构、状态或业务协作。"""
    title: Optional[str] = None
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None


class StyleLockResponse(BaseModel):
    """业务类：承载 StyleLockResponse 相关的数据结构、状态或业务协作。"""
    ok: bool
    status: Optional[str] = None
    story_bible: dict = Field(default_factory=dict)
    missing_assets: list[dict] = Field(default_factory=list)
    audit_reports: list[dict] = Field(default_factory=list)


class StyleLockWorkerStepRequest(BaseModel):
    """业务类：承载 StyleLockWorkerStepRequest 相关的数据结构、状态或业务协作。"""
    lease_id: str = "style-lock-worker"
    batch_size: int = Field(default=1, ge=1, le=20)


class StoryPlanWorkerStepRequest(BaseModel):
    """业务类：承载 StoryPlanWorkerStepRequest 相关的数据结构、状态或业务协作。"""
    lease_id: str = "story-plan-worker"
    batch_size: int = Field(default=1, ge=1, le=20)


class EpisodeScriptGenerationRequest(BaseModel):
    """业务类：承载 EpisodeScriptGenerationRequest 相关的数据结构、状态或业务协作。"""
    target_duration_seconds: int | None = Field(default=None, ge=1)
