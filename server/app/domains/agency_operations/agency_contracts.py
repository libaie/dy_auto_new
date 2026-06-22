"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_contracts 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any, Literal

try:
    from enum import StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 compatibility
    from enum import Enum

    class StrEnum(str, Enum):
        """业务类：承载 StrEnum 相关的数据结构、状态或业务协作。

        类参数：无显式类参数 承载该类的业务配置、状态或数据字段。
        """
        pass

from pydantic import BaseModel, Field


class AgencyExecutionStatus(StrEnum):
    """业务类：承载 AgencyExecutionStatus 相关的数据结构、状态或业务协作。

    类参数：cancelled、completed、failed、queued、running 承载该类的业务配置、状态或数据字段。
    """
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgencyInvocationResultStatus(StrEnum):
    """业务类：承载 AgencyInvocationResultStatus 相关的数据结构、状态或业务协作。

    类参数：blocked、failed、passed、pending、warn 承载该类的业务配置、状态或数据字段。
    """
    pending = "pending"
    passed = "passed"
    warn = "warn"
    blocked = "blocked"
    failed = "failed"


class AgencyStepStatus(StrEnum):
    """业务类：承载 AgencyStepStatus 相关的数据结构、状态或业务协作。

    类参数：blocked、completed、failed、pending、running、warning 承载该类的业务配置、状态或数据字段。
    """
    pending = "pending"
    running = "running"
    completed = "completed"
    warning = "warning"
    blocked = "blocked"
    failed = "failed"


class AgencyExpertSummary(BaseModel):
    """业务类：承载 AgencyExpertSummary 相关的数据结构、状态或业务协作。

    类参数：expert_id、legacy、name、phases、role_type、sha256、source_commit、source_path 承载该类的业务配置、状态或数据字段。
    """
    expert_id: str
    name: str
    role_type: str
    source_path: str
    source_commit: str
    sha256: str
    phases: list[str]
    legacy: bool = False


class AgencyInvocationSummary(BaseModel):
    """业务类：承载 AgencyInvocationSummary 相关的数据结构、状态或业务协作。

    类参数：decision、display_scope、duration_ms、error_code、evidence、execution_status、expert_id、findings、id、legacy、next_action、required_changes、result_status、role、stage、summary 承载该类的业务配置、状态或数据字段。
    """
    id: str
    stage: str
    expert_id: str
    role: str
    execution_status: AgencyExecutionStatus
    result_status: AgencyInvocationResultStatus
    summary: str = ""
    decision: str = ""
    findings: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_action: str = ""
    legacy: bool = False
    display_scope: Literal["current_team", "historical_audit"] = "current_team"
    duration_ms: int = 0
    error_code: str | None = None


class AgencyInvocationDetail(AgencyInvocationSummary):
    """业务类：承载 AgencyInvocationDetail 相关的数据结构、状态或业务协作。

    类参数：evidence、input_summary、model_config_snapshot、output_summary、repair_action、repair_route、repair_target_ids、repair_target_type、retry_scope、source_commit、source_path、source_repo、source_sha256、token_usage 承载该类的业务配置、状态或数据字段。
    """
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Any] = Field(default_factory=list)
    source_repo: str = "jnMetaCode/agency-agents-zh"
    source_commit: str
    source_path: str
    source_sha256: str
    model_config_snapshot: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    repair_action: str | None = None
    repair_route: str | None = None
    repair_target_type: str | None = None
    repair_target_ids: list[str] = Field(default_factory=list)
    retry_scope: str | None = None


class AgencyDecisionLogItem(BaseModel):
    """业务类：承载 AgencyDecisionLogItem 相关的数据结构、状态或业务协作。

    类参数：decision、display_scope、error_code、evidence、expert_id、findings、id、invocation_id、legacy、next_action、required_changes、result_status、role、stage 承载该类的业务配置、状态或数据字段。
    """
    id: str
    invocation_id: str
    stage: str
    expert_id: str
    role: str
    result_status: AgencyInvocationResultStatus
    decision: str = ""
    findings: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_action: str = ""
    error_code: str | None = None
    legacy: bool = False
    display_scope: Literal["current_team", "historical_audit"] = "current_team"


class AgencyStageGraphNode(BaseModel):
    """业务类：承载 AgencyStageGraphNode 相关的数据结构、状态或业务协作。

    类参数：invocation_ids、label、lead、qa、reviewers、stage、status 承载该类的业务配置、状态或数据字段。
    """
    stage: str
    label: str
    status: AgencyStepStatus
    reviewers: list[str] = Field(default_factory=list)
    lead: str | None = None
    qa: list[str] = Field(default_factory=list)
    invocation_ids: list[str] = Field(default_factory=list)


class AgencyConsoleResponse(BaseModel):
    """业务类：承载 AgencyConsoleResponse 相关的数据结构、状态或业务协作。

    类参数：agency_trace_status、decision_log、expert_invocations、expert_team、latest_run、ok、production_steps、series、stage_graph 承载该类的业务配置、状态或数据字段。
    """
    ok: bool = True
    series: dict[str, Any]
    latest_run: dict[str, Any] | None = None
    agency_trace_status: str
    expert_team: list[AgencyExpertSummary]
    stage_graph: list[AgencyStageGraphNode]
    expert_invocations: list[AgencyInvocationSummary]
    decision_log: list[AgencyDecisionLogItem]
    production_steps: list[dict[str, Any]]
