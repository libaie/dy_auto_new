"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_debate_audit 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.db.models.agency_operations import AgencyExpertInvocation
from app.db.models import ProductionAuditEvent, ProductionJob
from app.domains.agency_operations.agency_scorecard_contracts import normalize_scorecard, scorecard_blocks_stage
from app.domains.video_production.production_status import JOB_LEASED, JOB_QUEUED, JOB_RETRY_WAIT, JOB_RUNNING
from app.domains.agency_operations.agency_orchestrator import AgencyOrchestrator, _hash_context
from app.domains.video_production.production_queue_service import enqueue_job


DEBATE_SCHEMA_VERSION = "agency.debate.v1"
AUTO_REPAIR_STAGE = "agency_auto_repair"
DEBATE_STAGES = {
    "style_lock",
    "storyboard",
    "image_stage",
    "image_review",
    "video_stage",
    "video_review",
    "compose_preflight",
    "compose",
}
CRITIC_EXPERT_ID = "visual_storyteller"
DEFENDER_EXPERT_ID = "video_stage_quality_reviewer"
ACTIVE_REPAIR_JOB_STATUSES = {JOB_QUEUED, JOB_LEASED, JOB_RUNNING, JOB_RETRY_WAIT}


RuntimeInvoke = Callable[..., Awaitable[Any]]


async def run_debate_audit(
    db: Session,
    *,
    series_id: str,
    stage: str,
    stage_context: dict[str, Any],
    runtime_config: dict[str, Any],
    runtime_invoke: RuntimeInvoke | None = None,
    episode_id: str | None = None,
    run_id: str | None = None,
    production_plan_id: str | None = None,
    production_episode_id: str | None = None,
    production_segment_id: str | None = None,
    pipeline_run_id: str | None = None,
) -> dict[str, Any]:
    """业务函数：处理 run_debate_audit 对应的业务流程、校验或数据转换。"""
    orchestrator = AgencyOrchestrator(runtime_invoke=runtime_invoke, enable_debate=False)
    common = {
        "series_id": series_id,
        "episode_id": episode_id,
        "run_id": run_id,
        "production_plan_id": production_plan_id,
        "production_episode_id": production_episode_id,
        "production_segment_id": production_segment_id,
        "pipeline_run_id": pipeline_run_id,
        "stage": stage,
        "runtime_config": runtime_config,
    }

    first_critic = await _invoke_debate_role(
        db,
        orchestrator,
        common,
        stage_context=stage_context,
        round_number=1,
        expert_id=CRITIC_EXPERT_ID,
        role="crit",
        opponent_summary=None,
    )
    first_defender = await _invoke_debate_role(
        db,
        orchestrator,
        common,
        stage_context=stage_context,
        round_number=1,
        expert_id=DEFENDER_EXPERT_ID,
        role="def",
        opponent_summary=_summary_for_invocation(db, first_critic["id"]),
    )
    second_critic = await _invoke_debate_role(
        db,
        orchestrator,
        common,
        stage_context=stage_context,
        round_number=2,
        expert_id=CRITIC_EXPERT_ID,
        role="crit",
        opponent_summary=_summary_for_invocation(db, first_defender["id"]),
    )
    second_defender = await _invoke_debate_role(
        db,
        orchestrator,
        common,
        stage_context=stage_context,
        round_number=2,
        expert_id=DEFENDER_EXPERT_ID,
        role="def",
        opponent_summary=_summary_for_invocation(db, second_critic["id"]),
    )

    invocations = [first_critic, first_defender, second_critic, second_defender]
    critic_card, critic_has_scorecard = _scorecard_for_invocation(
        db,
        second_critic["id"],
        second_critic["result_status"],
    )
    defender_card, defender_has_scorecard = _scorecard_for_invocation(
        db,
        second_defender["id"],
        second_defender["result_status"],
    )
    critic_blocks = _result_blocks(second_critic, critic_card, critic_has_scorecard)
    defender_blocks = _result_blocks(second_defender, defender_card, defender_has_scorecard)
    missing_scorecards = []
    if not critic_has_scorecard:
        missing_scorecards.append("critic")
    if not defender_has_scorecard:
        missing_scorecards.append("defender")

    if critic_blocks == defender_blocks:
        debate_status = "consensus_fail" if critic_blocks else "consensus_pass"
    else:
        debate_status = "unresolved"

    stage_status = "blocked" if debate_status != "consensus_pass" else "completed"
    final_verdict = "block" if stage_status == "blocked" else "pass"
    repair_intent = _repair_intent_for_stage(stage, final_verdict)

    trace = {
        "stage": stage,
        "stage_status": stage_status,
        "invocation_ids": [item["id"] for item in invocations],
        "invocations": invocations,
        "debate": {
            "schema_version": DEBATE_SCHEMA_VERSION,
            "stage": stage,
            "status": debate_status,
            "rounds": 2,
            "critic_invocation_ids": [first_critic["id"], second_critic["id"]],
            "defender_invocation_ids": [first_defender["id"], second_defender["id"]],
            "critic_scorecard": critic_card,
            "defender_scorecard": defender_card,
            "missing_scorecards": missing_scorecards,
            "final_verdict": final_verdict,
            "repair_intent": repair_intent,
            "downgrade_reason": _downgrade_reason(debate_status, stage, missing_scorecards),
        },
    }
    if stage_status == "blocked":
        _record_repair_intent(
            db,
            stage=stage,
            stage_context=stage_context,
            repair_intent=repair_intent,
            series_id=series_id,
            run_id=run_id,
            production_plan_id=production_plan_id,
            production_episode_id=production_episode_id,
            production_segment_id=production_segment_id,
            debate_trace=trace["debate"],
        )
    return trace


async def _invoke_debate_role(
    db: Session,
    orchestrator: AgencyOrchestrator,
    common: dict[str, Any],
    *,
    stage_context: dict[str, Any],
    round_number: int,
    expert_id: str,
    role: str,
    opponent_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """业务函数：处理 _invoke_debate_role 对应的业务流程、校验或数据转换。"""
    context = {
        **stage_context,
        "debate": {
            "round": round_number,
            "role": "critic" if role == "crit" else "defender",
            "critic_expert_id": CRITIC_EXPERT_ID,
            "defender_expert_id": DEFENDER_EXPERT_ID,
            "opponent_summary": opponent_summary or {},
        },
    }
    return await orchestrator._invoke_one(
        db,
        expert_id=expert_id,
        role=role,
        stage_context=context,
        context_hash=_hash_context(context),
        **common,
    )


def _summary_for_invocation(db: Session, invocation_id: str) -> dict[str, Any]:
    """业务函数：处理 _summary_for_invocation 对应的业务流程、校验或数据转换。"""
    invocation = db.query(AgencyExpertInvocation).filter(AgencyExpertInvocation.id == invocation_id).first()
    if not invocation:
        return {}
    return {
        "expert_id": invocation.expert_id,
        "role": invocation.role,
        "result_status": invocation.result_status,
        "output_summary": invocation.output_summary_json or {},
    }


def _scorecard_for_invocation(db: Session, invocation_id: str, result_status: str) -> tuple[dict[str, Any], bool]:
    """业务函数：处理 _scorecard_for_invocation 对应的业务流程、校验或数据转换。"""
    invocation = db.query(AgencyExpertInvocation).filter(AgencyExpertInvocation.id == invocation_id).first()
    raw = ((invocation.output_summary_json or {}).get("scorecard") if invocation else None) or {}
    has_scorecard = isinstance(raw, dict) and bool(raw)
    card = normalize_scorecard(raw)
    if result_status in {"failed", "blocked"} and card["verdict"] == "pass":
        card["verdict"] = "fail"
    return card, has_scorecard


def _result_blocks(result: dict[str, Any], scorecard: dict[str, Any], has_scorecard: bool) -> bool:
    """业务函数：处理 _result_blocks 对应的业务流程、校验或数据转换。"""
    if result.get("result_status") in {"blocked", "failed"}:
        return True
    if not has_scorecard:
        return True
    return scorecard_blocks_stage(scorecard)


def _repair_intent_for_stage(stage: str, final_verdict: str) -> str:
    """业务函数：处理 _repair_intent_for_stage 对应的业务流程、校验或数据转换。"""
    if final_verdict == "pass":
        return "none"
    if stage.startswith("video"):
        return "regenerate_image"
    if stage == "image_review":
        return "inpainting"
    if stage == "image_stage":
        return "prompt_tune"
    return "prompt_tune"


def _downgrade_reason(status: str, stage: str, missing_scorecards: list[str] | None = None) -> str:
    """业务函数：处理 _downgrade_reason 对应的业务流程、校验或数据转换。"""
    if status == "consensus_pass":
        return ""
    if missing_scorecards:
        roles = ", ".join(missing_scorecards)
        return f"{stage} debate missing required scorecard from {roles}"
    if status == "unresolved":
        return f"{stage} debate stayed unresolved after two rounds"
    return f"{stage} debate reached blocking consensus"


def _record_repair_intent(
    db: Session,
    *,
    stage: str,
    stage_context: dict[str, Any],
    repair_intent: str,
    series_id: str,
    run_id: str | None,
    production_plan_id: str | None,
    production_episode_id: str | None,
    production_segment_id: str | None,
    debate_trace: dict[str, Any],
) -> None:
    """业务函数：处理 _record_repair_intent 对应的业务流程、校验或数据转换。"""
    repair_type = _repair_type_for_intent(stage, repair_intent)
    targets = _repair_targets(stage_context, production_segment_id=production_segment_id, fallback_id=run_id or series_id)
    created_job_ids: list[str] = []

    if production_plan_id:
        for target_type, target_id in targets:
            key_prefix = f"debate-repair:{run_id or 'no-run'}:{production_plan_id}:{stage}:{repair_type}:{target_type}:{target_id}:"
            existing = (
                db.query(ProductionJob)
                .filter(ProductionJob.idempotency_key.like(f"{key_prefix}%"))
                .filter(ProductionJob.status.in_(ACTIVE_REPAIR_JOB_STATUSES))
                .order_by(ProductionJob.created_at.desc())
                .first()
            )
            if existing:
                created_job_ids.append(existing.id)
                continue
            existing_count = (
                db.query(ProductionJob)
                .filter(ProductionJob.idempotency_key.like(f"{key_prefix}%"))
                .count()
            )
            # 这里把后续生产或返修动作放入统一队列，保证租约、重试和审计边界一致。
            job = enqueue_job(
                db,
                production_plan_id,
                target_type,
                target_id,
                f"{AUTO_REPAIR_STAGE}:{repair_type}",
                f"{key_prefix}cycle-{existing_count + 1}",
                priority=5,
                max_attempts=2,
                commit=False,
            )
            job.blocked_reason = f"debate:{repair_intent}"[:120]
            created_job_ids.append(job.id)

    db.add(ProductionAuditEvent(
        event_type="agency_debate_repair_intent",
        run_id=run_id,
        production_plan_id=production_plan_id,
        production_episode_id=production_episode_id,
        production_segment_id=production_segment_id,
        payload_json={
            "stage": stage,
            "repair_intent": repair_intent,
            "repair_type": repair_type,
            "targets": [{"target_type": target_type, "target_id": target_id} for target_type, target_id in targets],
            "job_ids": created_job_ids,
            "debate": debate_trace,
        },
    ))
    db.flush()


def _repair_type_for_intent(stage: str, repair_intent: str) -> str:
    """业务函数：处理 _repair_type_for_intent 对应的业务流程、校验或数据转换。"""
    if stage.startswith("video") or repair_intent == "regenerate_video":
        return "video_segment_failed"
    if repair_intent in {"prompt_tune", "backtrack_storyboard"}:
        return "storyboard_missing_references"
    return "image_generation_failed"


def _repair_targets(
    stage_context: dict[str, Any],
    *,
    production_segment_id: str | None,
    fallback_id: str,
) -> list[tuple[str, str]]:
    """业务函数：处理 _repair_targets 对应的业务流程、校验或数据转换。"""
    targets: list[tuple[str, str]] = []
    if production_segment_id:
        targets.append(("production_segment", production_segment_id))
    for item in _context_items(stage_context):
        if not isinstance(item, dict):
            continue
        target_id = item.get("production_segment_id") or item.get("target_id") or item.get("frame_id") or item.get("id")
        if target_id:
            targets.append(("production_segment", str(target_id)))
    if not targets:
        targets.append(("run", str(fallback_id)))
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        if target in seen:
            continue
        seen.add(target)
        deduped.append(target)
    return deduped


def _context_items(stage_context: dict[str, Any]) -> list[Any]:
    """业务函数：处理 _context_items 对应的业务流程、校验或数据转换。"""
    for key in ("frames", "segments", "shots"):
        value = stage_context.get(key)
        if isinstance(value, list):
            return value
    payload = stage_context.get("asset_review")
    if isinstance(payload, dict):
        return [payload]
    return []
