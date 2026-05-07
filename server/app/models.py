from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator
import uuid


class TaskType(str, Enum):
    NURTURE = "nurture"
    SEARCH_COMMENT = "search_comment"
    SEARCH_LIKE = "search_like"
    SEARCH_DM = "search_dm"
    REPLY_COMMENT = "reply_comment"
    COLLECT = "collect"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    account_id: str
    device_id: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    retry_count: int = 0
    chain_instance_id: Optional[str] = None
    step_order: Optional[int] = None


class AccountConfig(BaseModel):
    id: str
    nickname: str
    douyin_id: str
    status: str = "active"
    daily_limits: dict[str, int] = Field(default_factory=lambda: {
        "likes": 50,
        "comments": 20,
        "follows": 20,
        "dms": 10,
        "replies": 15,
    })


class SelectorStrategy(BaseModel):
    type: str  # text, id, desc, className, package, coordinate, image
    value: Optional[str] = None
    x_percent: Optional[float] = None
    y_percent: Optional[float] = None
    priority: int
    # image 类型专用字段
    template: Optional[str] = None  # 模板图片文件名
    threshold: Optional[float] = None  # 匹配阈值


class SelectorConfig(BaseModel):
    action_name: str
    platform_version: str = "default"
    strategies: list[SelectorStrategy]
    version: int = 1


class TaskCreateRequest(BaseModel):
    type: TaskType
    account_id: str
    device_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


class BatchTaskCreateRequest(BaseModel):
    type: TaskType
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None
    device_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        if not self.account_ids and not self.group_ids:
            raise ValueError("account_ids 和 group_ids 至少提供一个")
        return self


# --- 任务参数校验模型 ---

class ActionWeight(BaseModel):
    type: str = Field(..., pattern="^(browse_feed|like|comment|follow)$")
    weight: int = Field(..., ge=0, le=100)


class NurtureParams(BaseModel):
    duration: int = Field(default=30, ge=1, le=120, description="养号时长(分钟)")
    actions: list[ActionWeight] = Field(default_factory=lambda: [
        ActionWeight(type="browse_feed", weight=70),
        ActionWeight(type="like", weight=20),
        ActionWeight(type="follow", weight=10),
    ])


class SearchCommentParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=200, description="评论内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    count: int = Field(default=5, ge=1, le=20, description="处理数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class SearchLikeParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    count: int = Field(default=5, ge=1, le=30, description="点赞数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class SearchDMParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=500, description="私信内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    count: int = Field(default=5, ge=1, le=10, description="私信数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class ReplyCommentParams(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=500, description="私信内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    count: int = Field(default=5, ge=1, le=10, description="每个视频处理评论数")
    video_count: int = Field(default=3, ge=1, le=10, description="处理视频数")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")
    max_age_days: int = Field(default=5, ge=1, le=30, description="评论最大天数")
    max_follows: int = Field(default=20, ge=1, le=50, description="每日关注上限")
    max_dms: int = Field(default=10, ge=1, le=30, description="每日私信上限")


def _validate_nurture_params(params: dict) -> dict:
    """Accept both legacy (duration only) and V2 (sub_tasks) formats."""
    if "sub_tasks" in params:
        validated = NurtureParamsV2(**params)
        return validated.model_dump(exclude_none=True)
    else:
        validated = NurtureParams(**params)
        return validated.model_dump(exclude_none=True)


# 任务类型 -> 参数模型映射
TASK_PARAMS_VALIDATORS = {
    "nurture": _validate_nurture_params,
    "search_comment": SearchCommentParams,
    "search_like": SearchLikeParams,
    "search_dm": SearchDMParams,
    "reply_comment": ReplyCommentParams,
}


class TaskProgressReport(BaseModel):
    task_id: str
    step: str = ""          # 当前步骤描述，如 "处理视频 2/3"
    detail: str = ""        # 详情，如 "已回复 5/15 条评论"
    progress: float = 0.0   # 0.0-1.0 进度


class TaskResultReport(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    ui_snapshot: Optional[dict[str, Any]] = None


class PollResponse(BaseModel):
    task: Optional[Task] = None
    selectors_version: int = 1
    prompt_templates_version: int = 1
    proxy: Optional[dict[str, Any]] = None
    cancelled_task_id: Optional[str] = None
    anti_detect_config: Optional[dict[str, Any]] = None
    anti_detect_config_version: int = 1
    ai_config: Optional[dict[str, Any]] = None
    device_config: Optional[dict[str, Any]] = None


class DeviceRegisterRequest(BaseModel):
    device_id: str
    name: str
    os_version: str = ""
    app_version: str = ""
    screen_resolution: str = ""
    sdk_version: str = ""
    total_memory: Optional[int] = None
    manufacturer: str = ""
    product: str = ""
    device_model: str = ""
    hardware: str = ""
    display: str = ""


class DeviceRegisterResponse(BaseModel):
    device_id: str
    name: str
    status: str
    config: dict[str, Any]


class RiskReport(BaseModel):
    account_id: str
    risk_type: str  # captcha, rate_limit, account_risk, security_check
    detail: dict[str, Any] = Field(default_factory=dict)
    device_id: str = ""
    timestamp: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_in: int  # seconds


class AdminUser(BaseModel):
    username: str


class ContentTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="comment", pattern="^(comment|dm|reply)$")
    body: str = Field(..., min_length=1)
    variables: list[str] = Field(default_factory=list)


class ContentTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, pattern="^(comment|dm|reply)$")
    body: Optional[str] = Field(None, min_length=1)
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ContentTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    body: str
    variables: list[str]
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SensitiveWordCreate(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)


class SensitiveWordResponse(BaseModel):
    id: str
    word: str
    created_at: Optional[datetime] = None


class GenerateRequest(BaseModel):
    template_id: str
    context: dict[str, Any] = Field(default_factory=dict)  # {"keyword": "...", "username": "...", "video_title": "..."}


class GenerateResponse(BaseModel):
    content: str
    template_id: str


class DeviceGenerateRequest(BaseModel):
    template_id: str
    context: dict[str, str] = Field(default_factory=dict)


class DeviceGenerateResponse(BaseModel):
    content: str
    template_id: str


class DeviceAIProxyRequest(BaseModel):
    prompt: str
    max_tokens: int = 4096
    temperature: float = 0.7


class DeviceAIProxyResponse(BaseModel):
    content: str


class PairRequestCreate(BaseModel):
    device_id: str
    device_name: str
    os_version: str = ""
    app_version: str = ""
    screen_resolution: str = ""
    sdk_version: str = ""
    total_memory: Optional[int] = None
    manufacturer: str = ""
    product: str = ""
    device_model: str = ""
    hardware: str = ""
    display: str = ""


class PairRequestResponse(BaseModel):
    pairing_token: str
    status: str = "pending"


class PairStatusResponse(BaseModel):
    status: str  # pending, approved, rejected
    pairing_token: Optional[str] = None  # only for pending (from pair-request)
    secret: Optional[str] = None
    config: Optional[dict[str, Any]] = None


# --- 账号分组 ---

class AccountGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class AccountGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AccountGroupResponse(BaseModel):
    id: str
    name: str
    description: str
    member_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountGroupMemberRequest(BaseModel):
    account_ids: list[str] = Field(..., min_length=1)


# --- 任务链 ---

class ChainStep(BaseModel):
    step_order: int = Field(..., ge=1)
    type: TaskType
    label: str = Field(default="", max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class ChainTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    steps: list[ChainStep] = Field(..., min_length=1)


class ChainTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    steps: Optional[list[ChainStep]] = None


class ChainTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChainInstanceCreateRequest(BaseModel):
    template_id: str
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None
    device_id: Optional[str] = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        if not self.account_ids and not self.group_ids:
            raise ValueError("account_ids 和 group_ids 至少提供一个")
        return self


class ChainInstanceResponse(BaseModel):
    id: str
    template_id: str
    template_name: str = ""
    account_id: str
    account_nickname: str = ""
    device_id: str = ""
    current_step: int
    total_steps: int
    status: str
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# --- 养号 V2 ---

class NurtureSubTask(BaseModel):
    type: str = Field(..., pattern="^(browse|watch|like|comment|follow)$")
    count: int = Field(default=1, ge=1, le=100)
    content_template_id: Optional[str] = None


class NurtureParamsV2(BaseModel):
    sub_tasks: list[NurtureSubTask] = Field(..., min_length=1)
    completion_mode: str = Field(default="all", pattern="^(all|any)$")
    duration: int = Field(default=60, ge=1, le=240, description="最大时长(分钟)")
    keywords: Optional[list[str]] = Field(default=None, description="种子关键词，AI 扩展为关键词矩阵")
    keyword_matrix: Optional[list[str]] = Field(default=None, description="AI 扩展后的关键词矩阵（自动生成）")


# --- 关键词矩阵 ---

class KeywordMatrixRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=50)
    count: int = Field(default=10, ge=1, le=30)


class GenerateRegexRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)


class GenerateCleanPromptRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)


# --- 系统设置 ---

class SettingUpdate(BaseModel):
    settings: dict[str, str]


# --- 通道 (Channel) ---

class ChannelCreate(BaseModel):
    group_id: str
    task_type: TaskType
    account_mode: str = Field(default="round_robin", pattern="^(single_account|round_robin)$")
    account_id: Optional[str] = None
    keywords: list[str] = Field(..., min_length=1, max_length=500)
    params_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=300, ge=30, le=3600)
    delay_range: list[int] = Field(default=[3000, 8000])

    @model_validator(mode="after")
    def validate_single_account(self):
        if self.account_mode == "single_account" and not self.account_id:
            raise ValueError("single_account 模式下 account_id 必填")
        if len(self.delay_range) != 2 or self.delay_range[0] >= self.delay_range[1]:
            raise ValueError("delay_range 必须为 [min, max] 且 min < max")
        return self


class ChannelUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(paused|active|cancelled)$")


class ChannelItemUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(skipped|pending)$")


class ChannelAppendItems(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=500)


class ChannelItemResponse(BaseModel):
    id: str
    keyword: str
    account_id: str
    account_nickname: str = ""
    status: str
    assigned_device_id: str = ""
    device_name: str = ""
    task_id: str = ""
    queue_position: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChannelResponse(BaseModel):
    id: str
    group_id: str
    group_name: str = ""
    task_type: str
    status: str
    account_mode: str
    account_id: str = ""
    params_template: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = 300
    delay_range: list[int] = Field(default=[3000, 8000])
    total: int = 0
    pending: int = 0
    assigned: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ChannelDetailResponse(ChannelResponse):
    items: list[ChannelItemResponse] = []

# --- 采集上报 ---

class CollectCommentData(BaseModel):
    nickname: str
    content: str
    time_str: str = ""
    reply_count: str = ""
    like_count: str = ""
    dislike_count: str = ""
    location: str = ""
    is_author: bool = False


class CollectUserData(BaseModel):
    nickname: str
    douyin_id: str = ""
    likes_count: str = ""
    follow_count: str = ""
    fans_count: str = ""
    works_count: str = ""
    gender: str = ""
    age: str = ""
    ip_location: str = ""
    is_private: str = ""


class CollectReportRequest(BaseModel):
    task_id: str
    keyword: str
    comment: CollectCommentData
    user: CollectUserData | None = None

