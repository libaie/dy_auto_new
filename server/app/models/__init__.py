"""接口模型包。

集中声明旧版接口模型和任务参数结构，兼容设备端与管理端调用。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator
import uuid


class TaskType(str, Enum):
    """业务类：承载 TaskType 相关的数据结构、状态或业务协作。"""
    NURTURE = "nurture"
    SEARCH_COMMENT = "search_comment"
    SEARCH_LIKE = "search_like"
    SEARCH_DM = "search_dm"
    REPLY_COMMENT = "reply_comment"
    COLLECT = "collect"


class TaskStatus(str, Enum):
    """业务类：承载 TaskStatus 相关的数据结构、状态或业务协作。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """业务类：承载 Task 相关的数据结构、状态或业务协作。"""
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
    lease_id: Optional[str] = None


class AccountConfig(BaseModel):
    """业务类：承载 AccountConfig 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 SelectorStrategy 相关的数据结构、状态或业务协作。"""
    type: str  # text, id, desc, className, package, coordinate, image
    value: Optional[str] = None
    x_percent: Optional[float] = None
    y_percent: Optional[float] = None
    priority: int
    # image 类型专用字段
    template: Optional[str] = None  # 模板图片文件名
    threshold: Optional[float] = None  # 匹配阈值


class SelectorConfig(BaseModel):
    """业务类：承载 SelectorConfig 相关的数据结构、状态或业务协作。"""
    action_name: str
    platform_version: str = "default"
    strategies: list[SelectorStrategy]
    version: int = 1
    purpose: str = "locate"  # locate | extract | page_detect


class TaskCreateRequest(BaseModel):
    """业务类：承载 TaskCreateRequest 相关的数据结构、状态或业务协作。"""
    type: TaskType
    account_id: str
    device_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None


class BatchTaskCreateRequest(BaseModel):
    """业务类：承载 BatchTaskCreateRequest 相关的数据结构、状态或业务协作。"""
    type: TaskType
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None
    device_id: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: Optional[datetime] = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        """业务函数：处理 check_at_least_one 对应的业务流程、校验或数据转换。"""
        if not self.account_ids and not self.group_ids:
            raise ValueError("account_ids 和 group_ids 至少提供一个")
        return self


# --- 任务参数校验模型 ---

class ActionWeight(BaseModel):
    """业务类：承载 ActionWeight 相关的数据结构、状态或业务协作。"""
    type: str = Field(..., pattern="^(browse_feed|like|comment|follow)$")
    weight: int = Field(..., ge=0, le=100)


class NurtureParams(BaseModel):
    """业务类：承载 NurtureParams 相关的数据结构、状态或业务协作。"""
    duration: int = Field(default=30, ge=1, le=120, description="养号时长(分钟)")
    prompt_template_id: Optional[str] = Field(None, description="Prompt template ID")
    actions: list[ActionWeight] = Field(default_factory=lambda: [
        ActionWeight(type="browse_feed", weight=70),
        ActionWeight(type="like", weight=20),
        ActionWeight(type="follow", weight=10),
    ])


class SearchCommentParams(BaseModel):
    """业务类：承载 SearchCommentParams 相关的数据结构、状态或业务协作。"""
    keyword: str = Field("", min_length=0, max_length=200, description="搜索关键词（分享链接模式时可为空）")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    share_links: Optional[list[str]] = Field(None, description="分享链接列表，每个链接对应一个视频")
    content: Optional[str] = Field(None, max_length=200, description="评论内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=-1, description="每视频处理数量, -1=全量")
    video_count: int = Field(default=5, ge=-1, description="处理视频数, -1=全量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")
    max_age_days: int = Field(default=30, ge=-1, description="评论最大天数, -1=不限")
    max_age_unit: Optional[str] = Field(None, pattern="^(seconds|minutes|hours|days)$",
                                        description="时间单位, 默认 days")


class SearchLikeParams(BaseModel):
    """业务类：承载 SearchLikeParams 相关的数据结构、状态或业务协作。"""
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=1, le=30, description="点赞数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class SearchDMParams(BaseModel):
    """业务类：承载 SearchDMParams 相关的数据结构、状态或业务协作。"""
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=500, description="私信内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    dm_sequence_id: Optional[str] = Field(None, description="DM序列模板ID")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=1, le=50, description="私信数量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")


class ReplyCommentParams(BaseModel):
    """业务类：承载 ReplyCommentParams 相关的数据结构、状态或业务协作。"""
    keyword: str = Field(..., min_length=1, max_length=50, description="搜索关键词")
    keywords: Optional[list[str]] = Field(None, description="批量关键词（通道模式）")
    content: Optional[str] = Field(None, max_length=500, description="私信内容")
    content_template_id: Optional[str] = Field(None, description="内容模板ID")
    dm_sequence_id: Optional[str] = Field(None, description="DM序列模板ID")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    count: int = Field(default=5, ge=-1, description="每个视频处理评论数, -1=全量")
    video_count: int = Field(default=3, ge=-1, description="处理视频数, -1=全量")
    sort_by: Optional[str] = Field(None, pattern="^(latest|most_liked)$")
    max_age_days: int = Field(default=5, ge=-1, description="评论最大天数, -1=不限")
    max_age_unit: Optional[str] = Field(None, pattern="^(seconds|minutes|hours|days)$",
                                        description="时间单位, 默认 days")
    max_follows: int = Field(default=20, ge=1, le=50, description="每日关注上限")
    max_dms: int = Field(default=10, ge=1, le=30, description="每日私信上限")


def _validate_nurture_params(params: dict) -> dict:
    """业务函数：处理 _validate_nurture_params 对应的业务流程、校验或数据转换。"""
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
    "collect": SearchCommentParams,  # collect 复用和 search_comment 相同的参数
}


class TaskProgressReport(BaseModel):
    """业务类：承载 TaskProgressReport 相关的数据结构、状态或业务协作。"""
    task_id: str
    lease_id: Optional[str] = None
    step: str = ""          # 当前步骤描述，如 "处理视频 2/3"
    detail: str = ""        # 详情，如 "已回复 5/15 条评论"
    progress: float = 0.0   # 0.0-1.0 进度


class TaskResultReport(BaseModel):
    """业务类：承载 TaskResultReport 相关的数据结构、状态或业务协作。"""
    task_id: str
    lease_id: Optional[str] = None
    status: TaskStatus
    result: Optional[dict[str, Any]] = None
    ui_snapshot: Optional[dict[str, Any]] = None


class PollResponse(BaseModel):
    """业务类：承载 PollResponse 相关的数据结构、状态或业务协作。"""
    task: Optional[Task] = None
    selectors_version: int = 1
    prompt_templates_version: int = 1
    proxy: Optional[dict[str, Any]] = None
    cancelled_task_id: Optional[str] = None
    anti_detect_config: Optional[dict[str, Any]] = None
    anti_detect_config_version: int = 1
    ai_config: Optional[dict[str, Any]] = None
    device_config: Optional[dict[str, Any]] = None
    dm_sequences: Optional[list[dict[str, Any]]] = None
    server_date: Optional[str] = None


class DeviceRegisterRequest(BaseModel):
    """业务类：承载 DeviceRegisterRequest 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 DeviceRegisterResponse 相关的数据结构、状态或业务协作。"""
    device_id: str
    name: str
    status: str
    config: dict[str, Any]


class RiskReport(BaseModel):
    """业务类：承载 RiskReport 相关的数据结构、状态或业务协作。"""
    account_id: str
    risk_type: str  # captcha, rate_limit, account_risk, security_check
    detail: dict[str, Any] = Field(default_factory=dict)
    device_id: str = ""
    timestamp: str = ""


class LoginRequest(BaseModel):
    """业务类：承载 LoginRequest 相关的数据结构、状态或业务协作。"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """业务类：承载 LoginResponse 相关的数据结构、状态或业务协作。"""
    token: str
    expires_in: int  # seconds
    role: str = "admin"
    user_id: str = ""


class RegisterRequest(BaseModel):
    """业务类：承载 RegisterRequest 相关的数据结构、状态或业务协作。"""
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: Optional[str] = "operator"
    nickname: Optional[str] = None


class AdminUser(BaseModel):
    """业务类：承载 AdminUser 相关的数据结构、状态或业务协作。"""
    username: str


class ContentTemplateCreate(BaseModel):
    """业务类：承载 ContentTemplateCreate 相关的数据结构、状态或业务协作。"""
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="comment", pattern="^(comment|dm|reply)$")
    body: str = Field(..., min_length=1)
    variables: list[str] = Field(default_factory=list)


class ContentTemplateUpdate(BaseModel):
    """业务类：承载 ContentTemplateUpdate 相关的数据结构、状态或业务协作。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, pattern="^(comment|dm|reply)$")
    body: Optional[str] = Field(None, min_length=1)
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ContentTemplateResponse(BaseModel):
    """业务类：承载 ContentTemplateResponse 相关的数据结构、状态或业务协作。"""
    id: str
    name: str
    category: str
    body: str
    variables: list[str]
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SensitiveWordCreate(BaseModel):
    """业务类：承载 SensitiveWordCreate 相关的数据结构、状态或业务协作。"""
    word: str = Field(..., min_length=1, max_length=100)


class SensitiveWordResponse(BaseModel):
    """业务类：承载 SensitiveWordResponse 相关的数据结构、状态或业务协作。"""
    id: str
    word: str
    created_at: Optional[datetime] = None


class GenerateRequest(BaseModel):
    """业务类：承载 GenerateRequest 相关的数据结构、状态或业务协作。"""
    template_id: str
    context: dict[str, Any] = Field(default_factory=dict)  # {"keyword": "...", "username": "...", "video_title": "..."}


class GenerateResponse(BaseModel):
    """业务类：承载 GenerateResponse 相关的数据结构、状态或业务协作。"""
    content: str
    template_id: str


class DeviceGenerateRequest(BaseModel):
    """业务类：承载 DeviceGenerateRequest 相关的数据结构、状态或业务协作。"""
    template_id: str
    context: dict[str, str] = Field(default_factory=dict)


class DeviceGenerateResponse(BaseModel):
    """业务类：承载 DeviceGenerateResponse 相关的数据结构、状态或业务协作。"""
    content: str
    template_id: str


class DeviceAIProxyRequest(BaseModel):
    """业务类：承载 DeviceAIProxyRequest 相关的数据结构、状态或业务协作。"""
    prompt: str
    max_tokens: int = 4096
    temperature: float = 0.7


class DeviceAIProxyResponse(BaseModel):
    """业务类：承载 DeviceAIProxyResponse 相关的数据结构、状态或业务协作。"""
    content: str


class PairRequestCreate(BaseModel):
    """业务类：承载 PairRequestCreate 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 PairRequestResponse 相关的数据结构、状态或业务协作。"""
    pairing_token: str
    status: str = "pending"


class PairStatusResponse(BaseModel):
    """业务类：承载 PairStatusResponse 相关的数据结构、状态或业务协作。"""
    status: str  # pending, approved, rejected
    pairing_token: Optional[str] = None  # only for pending (from pair-request)
    secret: Optional[str] = None
    config: Optional[dict[str, Any]] = None


# --- 账号分组 ---

class AccountGroupCreate(BaseModel):
    """业务类：承载 AccountGroupCreate 相关的数据结构、状态或业务协作。"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class AccountGroupUpdate(BaseModel):
    """业务类：承载 AccountGroupUpdate 相关的数据结构、状态或业务协作。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AccountGroupResponse(BaseModel):
    """业务类：承载 AccountGroupResponse 相关的数据结构、状态或业务协作。"""
    id: str
    name: str
    description: str
    member_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountGroupMemberRequest(BaseModel):
    """业务类：承载 AccountGroupMemberRequest 相关的数据结构、状态或业务协作。"""
    account_ids: list[str] = Field(..., min_length=1)


# --- 任务链 ---

class ChainStep(BaseModel):
    """业务类：承载 ChainStep 相关的数据结构、状态或业务协作。"""
    step_order: int = Field(..., ge=1)
    type: TaskType
    label: str = Field(default="", max_length=100)
    params: dict[str, Any] = Field(default_factory=dict)


class ChainTemplateCreate(BaseModel):
    """业务类：承载 ChainTemplateCreate 相关的数据结构、状态或业务协作。"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    steps: list[ChainStep] = Field(..., min_length=1)


class ChainTemplateUpdate(BaseModel):
    """业务类：承载 ChainTemplateUpdate 相关的数据结构、状态或业务协作。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    steps: Optional[list[ChainStep]] = None


class ChainTemplateResponse(BaseModel):
    """业务类：承载 ChainTemplateResponse 相关的数据结构、状态或业务协作。"""
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChainInstanceCreateRequest(BaseModel):
    """业务类：承载 ChainInstanceCreateRequest 相关的数据结构、状态或业务协作。"""
    template_id: str
    account_ids: Optional[list[str]] = None
    group_ids: Optional[list[str]] = None
    device_id: Optional[str] = None

    @model_validator(mode="after")
    def check_at_least_one(self):
        """业务函数：处理 check_at_least_one 对应的业务流程、校验或数据转换。"""
        if not self.account_ids and not self.group_ids:
            raise ValueError("account_ids 和 group_ids 至少提供一个")
        return self


class ChainInstanceResponse(BaseModel):
    """业务类：承载 ChainInstanceResponse 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 NurtureSubTask 相关的数据结构、状态或业务协作。"""
    type: str = Field(..., pattern="^(browse|watch|like|comment|follow)$")
    count: int = Field(default=1, ge=1, le=100)
    content_template_id: Optional[str] = None


class NurtureParamsV2(BaseModel):
    """业务类：承载 NurtureParamsV2 相关的数据结构、状态或业务协作。"""
    sub_tasks: list[NurtureSubTask] = Field(..., min_length=1)
    completion_mode: str = Field(default="all", pattern="^(all|any)$")
    duration: int = Field(default=60, ge=1, le=240, description="最大时长(分钟)")
    keywords: Optional[list[str]] = Field(default=None, description="种子关键词，AI 扩展为关键词矩阵")
    keyword_matrix: Optional[list[str]] = Field(default=None, description="AI 扩展后的关键词矩阵（自动生成）")
    expand_count: Optional[int] = Field(default=None, ge=1, le=100, description="Keyword expansion count")
    prompt_template_id: Optional[str] = Field(None, description="Prompt template ID")


# --- 关键词矩阵 ---

class KeywordMatrixRequest(BaseModel):
    """业务类：承载 KeywordMatrixRequest 相关的数据结构、状态或业务协作。"""
    keyword: str = Field(..., min_length=1, max_length=50)
    count: int = Field(default=10, ge=1, le=30)


class GenerateRegexRequest(BaseModel):
    """业务类：承载 GenerateRegexRequest 相关的数据结构、状态或业务协作。"""
    description: str = Field(..., min_length=1, max_length=5000)


class GenerateCleanPromptRequest(BaseModel):
    """业务类：承载 GenerateCleanPromptRequest 相关的数据结构、状态或业务协作。"""
    description: str = Field(..., min_length=1, max_length=5000)


# --- 系统设置 ---

class SettingUpdate(BaseModel):
    """业务类：承载 SettingUpdate 相关的数据结构、状态或业务协作。"""
    settings: dict[str, str]


# --- 通道 (Channel) ---

class ChannelCreate(BaseModel):
    """业务类：承载 ChannelCreate 相关的数据结构、状态或业务协作。"""
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
        """业务函数：处理 validate_single_account 对应的业务流程、校验或数据转换。"""
        if self.account_mode == "single_account" and not self.account_id:
            raise ValueError("single_account 模式下 account_id 必填")
        if len(self.delay_range) != 2 or self.delay_range[0] >= self.delay_range[1]:
            raise ValueError("delay_range 必须为 [min, max] 且 min < max")
        return self


class ChannelUpdate(BaseModel):
    """业务类：承载 ChannelUpdate 相关的数据结构、状态或业务协作。"""
    status: Optional[str] = Field(None, pattern="^(paused|active|cancelled)$")


class ChannelItemUpdate(BaseModel):
    """业务类：承载 ChannelItemUpdate 相关的数据结构、状态或业务协作。"""
    status: Optional[str] = Field(None, pattern="^(skipped|pending)$")


class ChannelAppendItems(BaseModel):
    """业务类：承载 ChannelAppendItems 相关的数据结构、状态或业务协作。"""
    keywords: list[str] = Field(..., min_length=1, max_length=500)


class ChannelEditRequest(BaseModel):
    """业务类：承载 ChannelEditRequest 相关的数据结构、状态或业务协作。"""
    """PUT /api/channels/{id} — edit channel metadata (all fields optional)"""
    group_id: Optional[str] = None
    account_mode: Optional[str] = Field(None, pattern="^(single_account|round_robin)$")
    account_id: Optional[str] = None
    params_template: Optional[dict[str, Any]] = None
    cooldown_seconds: Optional[int] = Field(None, ge=30, le=3600)
    sync_to_items: bool = False


class ChannelItemEditRequest(BaseModel):
    """业务类：承载 ChannelItemEditRequest 相关的数据结构、状态或业务协作。"""
    """PUT /api/channel-items/{item_id} — edit a single pending/assigned item"""
    account_id: Optional[str] = None
    assigned_device_id: Optional[str] = None
    keyword: Optional[str] = Field(None, min_length=1, max_length=200)


class BatchEditRequest(BaseModel):
    """业务类：承载 BatchEditRequest 相关的数据结构、状态或业务协作。"""
    """PUT /api/channel-items/batch — batch edit pending/assigned items"""
    item_ids: list[str] = Field(..., min_length=1, max_length=500)
    account_id: Optional[str] = None
    assigned_device_id: Optional[str] = None


class ChannelItemResponse(BaseModel):
    """业务类：承载 ChannelItemResponse 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 ChannelResponse 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 ChannelDetailResponse 相关的数据结构、状态或业务协作。"""
    items: list[ChannelItemResponse] = []

# --- 采集上报 ---

class CollectCommentData(BaseModel):
    """业务类：承载 CollectCommentData 相关的数据结构、状态或业务协作。"""
    nickname: str
    content: str
    time_str: str = ""
    reply_count: str = ""
    like_count: str = ""
    dislike_count: str = ""
    location: str = ""
    is_author: bool = False
    ai_reply: str | None = None
    intended_province: str | None = None
    intended_city: str | None = None
    intended_attraction: str | None = None


class CollectUserData(BaseModel):
    """业务类：承载 CollectUserData 相关的数据结构、状态或业务协作。"""
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
    """业务类：承载 CollectReportRequest 相关的数据结构、状态或业务协作。"""
    task_id: str
    keyword: str
    comment: CollectCommentData
    user: CollectUserData | None = None
    data_source_type: int = 0  # 0=普通视频, 1=带货视频


class StatsIncrementRequest(BaseModel):
    """设备端增量统计上报——每个子操作完成后调用，idempotent per (task,device,type,target,index)"""
    task_id: str
    account_id: str
    task_type: str                          # search_like / search_comment / reply_comment / follow / search_dm / nurture / collect
    target_id: str = ""                     # 操作目标标识（评论昵称/用户ID），幂等 key 的一部分
    op_index: int = 0                       # 任务内操作序号，幂等 key 的一部分
    count: int = 1


# --- DM / Conversation models ---

class DMClaimRecipientRequest(BaseModel):
    """业务类：承载 DMClaimRecipientRequest 相关的数据结构、状态或业务协作。"""
    account_id: str
    recipient_douyin_id: str
    recipient_nickname: str


class DMClaimRecipientResponse(BaseModel):
    """业务类：承载 DMClaimRecipientResponse 相关的数据结构、状态或业务协作。"""
    claimed: bool
    conversation_id: str | None = None


class DMSendReportRequest(BaseModel):
    """业务类：承载 DMSendReportRequest 相关的数据结构、状态或业务协作。"""
    conversation_id: str
    task_id: str | None = None
    stage: str = "qualifying"
    intent: str | None = None
    keyword: str | None = None
    content: str
    dm_sequence_id: str | None = None
    message_order: int | None = None
    message_key: str | None = None
    status: str = "sent"
    error_message: str | None = None

class DMReleaseRecipientRequest(BaseModel):
    """业务类：承载 DMReleaseRecipientRequest 相关的数据结构、状态或业务协作。"""
    conversation_id: str


class DMReleaseRecipientResponse(BaseModel):
    """业务类：承载 DMReleaseRecipientResponse 相关的数据结构、状态或业务协作。"""
    released: bool

from app.models.script import (
    DramaticBeat,
    DramaticBeatList,
    DramaticBeatType,
    EpisodeScript,
    PipelineStage,
    SceneOutline,
    SceneOutlineList,
    VisualShot,
    VisualShotList,
)
from app.models.asset_anchor import (
    AnchorProviderPayload,
    AnchorReferenceImage,
    AnchorReferenceMode,
    AnchorStatus,
    CharacterAnchor,
    ComposedShotPrompt,
    SceneAnchor,
)
