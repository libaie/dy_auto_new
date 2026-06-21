"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_repair_classifier 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from app.domains.agency_operations.agency_repair_contracts import (
    PAID_REPAIR_TYPES,
    READABILITY_FALLBACK_EXPECTED,
    READABILITY_FALLBACK_REASON,
    RepairClassificationResult,
    RepairTask,
    action_for_task,
    looks_unreadable,
)


GENERIC_FINDING_PHRASES = (
    "已记录审查发现",
    "已记录异常结论",
    "等待下一步处理",
)


def _manual_task(stage: str, series_id: str | None, *, reason: str = READABILITY_FALLBACK_REASON) -> RepairTask:
    label, route = action_for_task("manual_incomplete_repair_task", "manual", None)
    return RepairTask(
        type="manual_incomplete_repair_task",
        stage=stage,
        target_type="manual",
        series_id=series_id,
        auto_execute=False,
        requires_paid_provider=False,
        reason=reason,
        expected_result=READABILITY_FALLBACK_EXPECTED,
        repair_action_label=label,
        repair_route=route,
    )


def classify_repair_tasks(
    output_summary: dict[str, Any] | None,
    *,
    stage: str,
    series_id: str | None,
) -> RepairClassificationResult:
    output = output_summary or {}
    raw_tasks = output.get("repair_tasks") or []
    tasks: list[RepairTask] = []

    if not isinstance(raw_tasks, list) or not raw_tasks:
        summary = _summary_text(output)
        if _needs_manual_from_summary(summary):
            tasks.append(_manual_task(stage, series_id))
        return _result(tasks)

    for raw in raw_tasks:
        if not isinstance(raw, dict):
            tasks.append(_manual_task(stage, series_id))
            continue
        task_type = str(raw.get("type") or "").strip() or "manual_incomplete_repair_task"
        target_type = str(raw.get("target_type") or "manual").strip()
        target_id = raw.get("target_id")
        label, route = action_for_task(task_type, target_type, str(target_id) if target_id else None)
        task = RepairTask(
            type=task_type,
            stage=str(raw.get("stage") or stage),
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            series_id=str(raw.get("series_id") or series_id) if (raw.get("series_id") or series_id) else None,
            auto_execute=bool(raw.get("auto_execute", False)),
            requires_paid_provider=bool(raw.get("requires_paid_provider", task_type in PAID_REPAIR_TYPES)),
            budget_authorized=bool(raw.get("budget_authorized", False)),
            priority=str(raw.get("priority") or "normal"),
            estimated_cost=float(raw.get("estimated_cost") or 0.0),
            reason=str(raw.get("reason") or raw.get("finding") or READABILITY_FALLBACK_REASON),
            expected_result=str(raw.get("expected_result") or "完成返修后重新进入审查"),
            repair_action_label=str(raw.get("repair_action_label") or label),
            repair_route=raw.get("repair_route") or route,
            affected_ids=list(raw.get("affected_ids") or ([target_id] if target_id else [])),
            metadata=dict(raw.get("metadata") or {}),
        )
        if task.type == "manual_incomplete_repair_task" or not task.target_id:
            task.auto_execute = False
            task.requires_paid_provider = False
        tasks.append(task)

    return _result(tasks)


def _result(tasks: list[RepairTask]) -> RepairClassificationResult:
    auto_tasks = [task for task in tasks if task.auto_execute]
    return RepairClassificationResult(
        repairable=bool(auto_tasks),
        manual_gate_required=bool(tasks),
        blocked_reason=None if auto_tasks else (READABILITY_FALLBACK_REASON if tasks else None),
        repair_tasks=tasks,
    )


def _summary_text(output: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("decision", "summary", "finding", "findings", "required_changes", "next_action"):
        value = output.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item)
        elif value:
            values.append(str(value))
    return " ".join(values).strip()


def _needs_manual_from_summary(summary: str) -> bool:
    if not summary:
        return False
    if looks_unreadable(summary):
        return True
    if any(phrase in summary for phrase in GENERIC_FINDING_PHRASES):
        return True
    keywords = ("缺少", "缺失", "失败", "异常", "需要", "重绘", "补齐", "阻断", "超时")
    return any(word in summary for word in keywords)
