"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_orchestrator 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from sqlalchemy.orm import Session

from app.domains.agency_operations.agency_manifest import (
    AgencyManifestError,
    get_expert,
    load_manifest,
    verify_manifest,
)
from app.domains.agency_operations.agency_persistence import (
    create_or_resume_invocation,
    finalize_invocation_and_audit,
)
from app.domains.agency_operations.agency_runtime import (
    AgencyRuntimeError,
    AgencySkillRuntime,
)
from app.domains.agency_operations.agency_runtime_contracts import (
    OPENAI_CHAT_COMPLETIONS_PROTOCOL,
    OPENAI_COMPATIBLE_PROVIDERS,
)


STAGE_DAG = {
    "story_planning": {
        "reviewers": ["narrative_designer", "douyin_strategist"],
        "lead": "story_generator",
        "qa": [],
    },
    "style_lock": {
        "reviewers": ["image_prompt_engineer", "short_video_editing_coach"],
        "lead": "visual_storyteller",
        "qa": ["style_lock_quality_reviewer"],
    },
    "storyboard": {
        "reviewers": ["visual_storyteller", "short_video_editing_coach", "douyin_strategist"],
        "lead": "narrative_designer",
        "qa": ["storyboard_quality_reviewer"],
    },
    "image_stage": {
        "reviewers": ["visual_storyteller", "prompt_engineer"],
        "lead": "image_prompt_engineer",
        "qa": ["image_stage_quality_reviewer"],
    },
    "image_review": {
        "reviewers": ["image_prompt_engineer"],
        "lead": "visual_storyteller",
        "qa": ["image_review_quality_reviewer"],
    },
    "video_stage": {
        "reviewers": ["prompt_engineer", "visual_storyteller"],
        "lead": "short_video_editing_coach",
        "qa": ["video_stage_quality_reviewer"],
    },
    "video_review": {
        "reviewers": ["video_optimization_specialist"],
        "lead": "short_video_editing_coach",
        "qa": ["video_review_quality_reviewer"],
    },
    "compose_preflight": {
        "reviewers": ["douyin_strategist", "video_optimization_specialist"],
        "lead": "short_video_editing_coach",
        "qa": [],
    },
    "compose": {
        "reviewers": ["douyin_strategist", "video_optimization_specialist"],
        "lead": "short_video_editing_coach",
        "qa": ["compose_quality_reviewer"],
    },
}

TERMINAL_EXECUTION_STATUSES = {"completed", "failed"}


@dataclass(frozen=True)
class _PreparedInvocation:
    id: str
    role: str
    expert_id: str
    execution_status: str
    result_status: str
    is_terminal: bool


def _hash_context(context: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except TypeError as exc:
        raise ValueError("stage_context must be JSON-serializable for agency idempotency hashing") from exc
    return hashlib.sha256(encoded).hexdigest()[:24]


def _source(expert_id: str) -> dict[str, str]:
    manifest = load_manifest()
    expert = get_expert(expert_id)
    return {
        "repo": manifest.source_repo,
        "commit": manifest.source_commit,
        "path": expert.source_path,
        "sha256": expert.sha256,
    }


def _run_scope(
    *,
    run_id: str | None,
    production_plan_id: str | None,
    production_episode_id: str | None,
    production_segment_id: str | None,
    pipeline_run_id: str | None,
) -> str:
    return (
        run_id
        or pipeline_run_id
        or production_segment_id
        or production_episode_id
        or production_plan_id
        or "no-run"
    )


def _idempotency_key(
    *,
    series_id: str,
    run_scope: str,
    stage: str,
    role: str,
    expert_id: str,
    context_hash: str,
) -> str:
    return f"agency:{series_id}:{run_scope}:{stage}:{role}:{expert_id}:{context_hash}"


def _stage_status(results: list[dict[str, Any]]) -> str:
    if any(item["result_status"] == "blocked" for item in results):
        return "blocked"
    if any(item["result_status"] == "failed" for item in results):
        return "failed"
    if any(item["result_status"] == "warn" for item in results):
        return "warning"
    return "completed"


def _runtime_config_value(config: dict[str, Any], key: str, default: Any = "") -> Any:
    nested = config.get("config")
    if isinstance(nested, dict) and key in nested:
        return nested[key]
    return config.get(key, default)


def _runtime_config_blocker(stage: str, runtime_config: dict[str, Any]) -> dict[str, Any] | None:
    protocol = str(_runtime_config_value(runtime_config, "protocol", "") or "").lower()
    provider = str(runtime_config.get("provider") or "").lower()
    if protocol != OPENAI_CHAT_COMPLETIONS_PROTOCOL and provider not in OPENAI_COMPATIBLE_PROVIDERS:
        return None

    missing = []
    if not str(runtime_config.get("base_url") or "").strip():
        missing.append("base_url")
    if not str(runtime_config.get("api_key") or "").strip():
        missing.append("api_key")
    if not str(runtime_config.get("model") or runtime_config.get("model_id") or "").strip():
        missing.append("model")
    if not missing:
        return None

    return {
        "stage": stage,
        "stage_status": "blocked",
        "invocation_ids": [],
        "invocations": [],
        "error_code": "EXPERT_MODEL_CONFIG_MISSING",
        "error_message": f"Agency expert runtime model requires {', '.join(missing)}.",
    }


def _manifest_blocker(stage: str) -> dict[str, Any] | None:
    try:
        verify_manifest()
    except AgencyManifestError:
        return {
            "stage": stage,
            "stage_status": "blocked",
            "invocation_ids": [],
            "invocations": [],
            "error_code": "AGENCY_MANIFEST_INVALID",
            "error_message": "Agency expert manifest is invalid. Please refresh embedded expert assets.",
        }
    return None


class AgencyOrchestrator:
    def __init__(
        self,
        runtime_invoke: Callable[..., Awaitable[Any]] | None = None,
        reviewer_concurrency: int = 1,
        enable_debate: bool = True,
    ):
        self.runtime = AgencySkillRuntime()
        self.runtime_invoke = runtime_invoke or self.runtime.invoke
        self.reviewer_concurrency = max(1, reviewer_concurrency)
        self.enable_debate = enable_debate

    async def run_style_lock_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "style_lock", **kwargs)

    async def run_story_planning_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "story_planning", **kwargs)

    async def run_storyboard_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "storyboard", **kwargs)

    async def run_image_stage_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "image_stage", **kwargs)

    async def run_image_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "image_review", **kwargs)

    async def run_video_stage_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "video_stage", **kwargs)

    async def run_video_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "video_review", **kwargs)

    async def run_compose_preflight_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "compose_preflight", **kwargs)

    async def run_compose_review(self, db: Session, **kwargs) -> dict[str, Any]:
        return await self._run_stage(db, "compose", **kwargs)

    async def _call_runtime(self, **kwargs) -> Any:
        result = self.runtime_invoke(**kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _invoke_one(
        self,
        db: Session,
        *,
        series_id: str,
        stage: str,
        expert_id: str,
        role: str,
        stage_context: dict[str, Any],
        runtime_config: dict[str, Any],
        context_hash: str,
        episode_id: str | None = None,
        run_id: str | None = None,
        production_plan_id: str | None = None,
        production_episode_id: str | None = None,
        production_segment_id: str | None = None,
        pipeline_run_id: str | None = None,
    ) -> dict[str, Any]:
        prepared = self._prepare_invocation(
            db,
            series_id=series_id,
            episode_id=episode_id,
            run_id=run_id,
            production_plan_id=production_plan_id,
            production_episode_id=production_episode_id,
            production_segment_id=production_segment_id,
            pipeline_run_id=pipeline_run_id,
            stage=stage,
            expert_id=expert_id,
            role=role,
            stage_context=stage_context,
            context_hash=context_hash,
        )
        if prepared.is_terminal:
            return self._result_from_prepared(prepared)

        return await self._run_and_finalize_invocation(
            db,
            prepared=prepared,
            stage=stage,
            role=role,
            expert_id=expert_id,
            stage_context=stage_context,
            runtime_config=runtime_config,
        )

    def _prepare_invocation(
        self,
        db: Session,
        *,
        series_id: str,
        stage: str,
        expert_id: str,
        role: str,
        stage_context: dict[str, Any],
        context_hash: str,
        episode_id: str | None = None,
        run_id: str | None = None,
        production_plan_id: str | None = None,
        production_episode_id: str | None = None,
        production_segment_id: str | None = None,
        pipeline_run_id: str | None = None,
    ) -> _PreparedInvocation:
        run_scope = _run_scope(
            run_id=run_id,
            production_plan_id=production_plan_id,
            production_episode_id=production_episode_id,
            production_segment_id=production_segment_id,
            pipeline_run_id=pipeline_run_id,
        )
        invocation = create_or_resume_invocation(
            db,
            idempotency_key=_idempotency_key(
                series_id=series_id,
                run_scope=run_scope,
                stage=stage,
                role=role,
                expert_id=expert_id,
                context_hash=context_hash,
            ),
            series_id=series_id,
            episode_id=episode_id,
            run_id=run_id,
            production_plan_id=production_plan_id,
            production_episode_id=production_episode_id,
            production_segment_id=production_segment_id,
            pipeline_run_id=pipeline_run_id,
            stage=stage,
            expert_id=expert_id,
            role=role,
            source=_source(expert_id),
            input_summary=stage_context,
        )
        return _PreparedInvocation(
            id=invocation.id,
            role=role,
            expert_id=expert_id,
            execution_status=invocation.execution_status,
            result_status=invocation.result_status,
            is_terminal=invocation.execution_status in TERMINAL_EXECUTION_STATUSES,
        )

    def _result_from_prepared(self, prepared: _PreparedInvocation) -> dict[str, Any]:
        return {
            "id": prepared.id,
            "role": prepared.role,
            "expert_id": prepared.expert_id,
            "execution_status": prepared.execution_status,
            "result_status": prepared.result_status,
        }

    async def _run_prepared_runtime(
        self,
        runtime_db: Session | None,
        *,
        prepared: _PreparedInvocation,
        stage: str,
        role: str,
        expert_id: str,
        stage_context: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> tuple[_PreparedInvocation, Any | None, AgencyRuntimeError | None]:
        try:
            result = await self._call_runtime(
                db=runtime_db,
                expert_id=expert_id,
                stage=stage,
                role=role,
                stage_context=stage_context,
                runtime_config=runtime_config,
            )
            return prepared, result, None
        except AgencyRuntimeError as exc:
            return prepared, None, exc
        except Exception as exc:
            return prepared, None, AgencyRuntimeError("EXPERT_RUNTIME_UNEXPECTED", str(exc))

    def _finalize_prepared_runtime(
        self,
        db: Session,
        prepared: _PreparedInvocation,
        result: Any | None,
        runtime_error: AgencyRuntimeError | None,
    ) -> dict[str, Any]:
        if runtime_error is None:
            try:
                finalized = finalize_invocation_and_audit(
                    db,
                    invocation_id=prepared.id,
                    result_status=result.result_status,
                    output_summary=result.output_summary,
                    evidence=result.evidence,
                    token_usage=result.token_usage,
                    model_config_snapshot=result.model_config_snapshot,
                )
            except Exception as exc:
                finalized = finalize_invocation_and_audit(
                    db,
                    invocation_id=prepared.id,
                    result_status="failed",
                    output_summary={
                        "decision": "failed",
                        "findings": [],
                        "recommendations": [],
                        "required_changes": [],
                    },
                    evidence=[],
                    error_code="EXPERT_RUNTIME_UNEXPECTED",
                    error_message=str(exc),
                )
        else:
            finalized = finalize_invocation_and_audit(
                db,
                invocation_id=prepared.id,
                result_status="failed",
                output_summary={
                    "decision": "failed",
                    "findings": [],
                    "recommendations": [],
                    "required_changes": [],
                },
                evidence=[],
                error_code=runtime_error.error_code,
                error_message=str(runtime_error),
            )

        return {
            "id": finalized.id,
            "role": prepared.role,
            "expert_id": prepared.expert_id,
            "execution_status": finalized.execution_status,
            "result_status": finalized.result_status,
        }

    async def _run_and_finalize_invocation(
        self,
        db: Session,
        *,
        prepared: _PreparedInvocation,
        stage: str,
        role: str,
        expert_id: str,
        stage_context: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        prepared, result, runtime_error = await self._run_prepared_runtime(
            None,
            prepared=prepared,
            stage=stage,
            role=role,
            expert_id=expert_id,
            stage_context=stage_context,
            runtime_config=runtime_config,
        )
        return self._finalize_prepared_runtime(db, prepared, result, runtime_error)

    async def _invoke_reviewers(
        self,
        db: Session,
        *,
        expert_ids: list[str],
        stage_context: dict[str, Any],
        common: dict[str, Any],
    ) -> list[dict[str, Any]]:
        prepare_common = {key: value for key, value in common.items() if key != "runtime_config"}
        prepared_reviewers = [
            self._prepare_invocation(
                db,
                expert_id=expert_id,
                role="reviewer",
                stage_context=stage_context,
                **prepare_common,
            )
            for expert_id in expert_ids
        ]
        semaphore = asyncio.Semaphore(self.reviewer_concurrency)

        async def run_with_bound(prepared: _PreparedInvocation):
            async with semaphore:
                return await self._run_prepared_runtime(
                    None,
                    prepared=prepared,
                    stage=common["stage"],
                    role="reviewer",
                    expert_id=prepared.expert_id,
                    stage_context=stage_context,
                    runtime_config=common["runtime_config"],
                )

        runtime_tasks = [
            run_with_bound(prepared)
            for prepared in prepared_reviewers
            if not prepared.is_terminal
        ]
        runtime_results = iter(await asyncio.gather(*runtime_tasks)) if runtime_tasks else iter(())

        reviewer_results = []
        for prepared in prepared_reviewers:
            if prepared.is_terminal:
                reviewer_results.append(self._result_from_prepared(prepared))
            else:
                runtime_prepared, result, runtime_error = next(runtime_results)
                reviewer_results.append(
                    self._finalize_prepared_runtime(db, runtime_prepared, result, runtime_error)
                )
        return reviewer_results

    async def _run_stage(
        self,
        db: Session,
        stage: str,
        *,
        series_id: str,
        stage_context: dict[str, Any],
        runtime_config: dict[str, Any],
        episode_id: str | None = None,
        run_id: str | None = None,
        production_plan_id: str | None = None,
        production_episode_id: str | None = None,
        production_segment_id: str | None = None,
        pipeline_run_id: str | None = None,
    ) -> dict[str, Any]:
        spec = STAGE_DAG[stage]
        manifest_trace = _manifest_blocker(stage)
        if manifest_trace:
            return manifest_trace

        blocked_trace = _runtime_config_blocker(stage, runtime_config)
        if blocked_trace:
            return blocked_trace

        context_hash = _hash_context(stage_context)
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
            "context_hash": context_hash,
        }

        reviewer_results = await self._invoke_reviewers(
            db,
            expert_ids=spec["reviewers"],
            stage_context=stage_context,
            common=common,
        )

        lead_context = {
            **stage_context,
            "reviewer_invocation_ids": [item["id"] for item in reviewer_results],
        }
        lead_result = await self._invoke_one(
            db,
            expert_id=spec["lead"],
            role="lead",
            stage_context=lead_context,
            **common,
        )

        qa_results = []
        for expert_id in spec["qa"]:
            qa_context = {**stage_context, "lead_invocation_id": lead_result["id"]}
            qa_results.append(
                await self._invoke_one(
                    db,
                    expert_id=expert_id,
                    role="qa",
                    stage_context=qa_context,
                    **common,
                )
            )

        all_results = [*reviewer_results, lead_result, *qa_results]
        trace = {
            "stage": stage,
            "stage_status": _stage_status(all_results),
            "invocation_ids": [item["id"] for item in all_results],
            "invocations": all_results,
        }
        if self.enable_debate:
            from app.domains.agency_operations.agency_debate_audit import DEBATE_STAGES

            if stage not in DEBATE_STAGES:
                return trace
            debate_trace = await self._run_stage_debate(
                db,
                stage=stage,
                stage_context=stage_context,
                common=common,
            )
            trace = _merge_debate_trace(trace, debate_trace)
        return trace

    async def _run_stage_debate(
        self,
        db: Session,
        *,
        stage: str,
        stage_context: dict[str, Any],
        common: dict[str, Any],
    ) -> dict[str, Any]:
        from app.domains.agency_operations.agency_debate_audit import run_debate_audit

        return await run_debate_audit(
            db,
            series_id=common["series_id"],
            episode_id=common.get("episode_id"),
            run_id=common.get("run_id"),
            production_plan_id=common.get("production_plan_id"),
            production_episode_id=common.get("production_episode_id"),
            production_segment_id=common.get("production_segment_id"),
            pipeline_run_id=common.get("pipeline_run_id"),
            stage=stage,
            stage_context=stage_context,
            runtime_config=common["runtime_config"],
            runtime_invoke=self.runtime_invoke,
        )


def _merge_debate_trace(trace: dict[str, Any], debate_trace: dict[str, Any]) -> dict[str, Any]:
    merged = dict(trace or {})
    merged["invocation_ids"] = [
        *(trace or {}).get("invocation_ids", []),
        *debate_trace.get("invocation_ids", []),
    ]
    merged["invocations"] = [
        *(trace or {}).get("invocations", []),
        *debate_trace.get("invocations", []),
    ]
    if debate_trace.get("debate"):
        merged["debate"] = debate_trace["debate"]
    if debate_trace.get("stage_status") in {"blocked", "failed"}:
        merged["stage_status"] = debate_trace["stage_status"]
        merged["error_code"] = "AGENCY_DEBATE_BLOCKED"
        merged["error_message"] = (debate_trace.get("debate") or {}).get("downgrade_reason") or "Agency debate blocked the stage."
    return merged
