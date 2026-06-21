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
        pass

from pydantic import BaseModel, Field


class AgencyExecutionStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgencyInvocationResultStatus(StrEnum):
    pending = "pending"
    passed = "passed"
    warn = "warn"
    blocked = "blocked"
    failed = "failed"


class AgencyStepStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    warning = "warning"
    blocked = "blocked"
    failed = "failed"


class AgencyExpertSummary(BaseModel):
    expert_id: str
    name: str
    role_type: str
    source_path: str
    source_commit: str
    sha256: str
    phases: list[str]
    legacy: bool = False


class AgencyInvocationSummary(BaseModel):
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
    stage: str
    label: str
    status: AgencyStepStatus
    reviewers: list[str] = Field(default_factory=list)
    lead: str | None = None
    qa: list[str] = Field(default_factory=list)
    invocation_ids: list[str] = Field(default_factory=list)


class AgencyConsoleResponse(BaseModel):
    ok: bool = True
    series: dict[str, Any]
    latest_run: dict[str, Any] | None = None
    agency_trace_status: str
    expert_team: list[AgencyExpertSummary]
    stage_graph: list[AgencyStageGraphNode]
    expert_invocations: list[AgencyInvocationSummary]
    decision_log: list[AgencyDecisionLogItem]
    production_steps: list[dict[str, Any]]
