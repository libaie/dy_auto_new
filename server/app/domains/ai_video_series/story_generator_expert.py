"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 story_generator_expert 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Awaitable, Callable

import httpx
import openai
from sqlalchemy.orm import Session

from app.domains.agency_operations.agency_manifest import get_expert, load_manifest, read_expert_markdown
from app.domains.agency_operations.agency_persistence import create_or_resume_invocation, finalize_invocation_and_audit
from app.domains.agency_operations.agency_runtime import (
    AgencyRuntimeError,
)
from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools
from app.domains.model_configuration.runtime_model_config import redact_runtime_model_config, resolve_runtime_model_config


STORY_GENERATOR_EXPERT_ID = "story_generator"
STORY_PLANNING_STAGE = "story_planning"
SCRIPT_GENERATION_SCENE = "script_generation"


@dataclass(frozen=True)
class StoryGeneratorResult:
    """业务类：承载 StoryGeneratorResult 相关的数据结构、状态或业务协作。"""
    parsed: dict[str, Any]
    source_type: str
    model_trace: dict[str, Any]


StoryModelClientResponse = str | dict[str, Any]
StoryModelClient = Callable[
    [str, str, dict[str, Any], dict[str, Any] | None],
    Awaitable[StoryModelClientResponse],
]


STORY_PLAN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "required": ["series_story_plan", "season_arc", "episode_outlines"],
    "properties": {
        "series_story_plan": {"type": "object"},
        "season_arc": {"type": "object"},
        "continuity_ledger": {"type": "object"},
        "episode_outlines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["episode_number", "title", "character_ids", "scene_ids"],
                "properties": {
                    "episode_number": {"type": "integer"},
                    "title": {"type": "string"},
                    "character_ids": {"type": "array", "items": {"type": "string"}},
                    "scene_ids": {"type": "array", "items": {"type": "string"}},
                    "asset_usage": {"type": "object"},
                    "generated_assets": {"type": "object"},
                },
            },
        },
    },
}


def _source(expert_id: str) -> dict[str, str]:
    """业务函数：处理 _source 对应的业务流程、校验或数据转换。"""
    manifest = load_manifest()
    expert = get_expert(expert_id)
    return {
        "repo": manifest.source_repo,
        "commit": manifest.source_commit,
        "path": expert.source_path,
        "sha256": expert.sha256,
    }


def _context_hash(context: dict[str, Any]) -> str:
    """业务函数：处理 _context_hash 对应的业务流程、校验或数据转换。"""
    encoded = json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def _supports_json_schema_response(config: dict[str, Any]) -> bool:
    """业务函数：处理 _supports_json_schema_response 对应的业务流程、校验或数据转换。"""
    nested = config.get("config") if isinstance(config.get("config"), dict) else {}
    for source in (config, nested):
        for key in ("supports_json_schema", "json_schema_response", "response_format_json_schema"):
            if bool(source.get(key)):
                return True
    return False


def _response_format(config: dict[str, Any]) -> dict[str, Any] | None:
    """业务函数：处理 _response_format 对应的业务流程、校验或数据转换。"""
    if not _supports_json_schema_response(config):
        return None
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "series_story_plan",
            "strict": True,
            "schema": STORY_PLAN_OUTPUT_SCHEMA,
        },
    }


def _split_model_response(response: StoryModelClientResponse) -> tuple[str, dict[str, Any]]:
    """业务函数：处理 _split_model_response 对应的业务流程、校验或数据转换。"""
    if isinstance(response, str):
        return response, {}
    if isinstance(response, dict):
        content = response.get("content")
        token_usage = response.get("token_usage") or {}
        if isinstance(content, str) and isinstance(token_usage, dict):
            return content, token_usage
    raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "Story generator response must contain JSON content.")


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    """业务函数：处理 _parse_json_object 对应的业务流程、校验或数据转换。"""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "Story generator output was empty.")
    text = raw_text.strip()
    candidates = [text]
    if "```" in text:
        for part in text.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate:
                candidates.append(candidate)

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed

        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[index:])
            except JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "Story generator output was not valid JSON.")


def _validate_story_payload(parsed: dict[str, Any]) -> None:
    """业务函数：处理 _validate_story_payload 对应的业务流程、校验或数据转换。"""
    if not isinstance(parsed.get("series_story_plan"), dict):
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "Story payload missing series_story_plan object.")
    if not isinstance(parsed.get("season_arc"), dict):
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "Story payload missing season_arc object.")
    if not isinstance(parsed.get("episode_outlines"), list):
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "Story payload missing episode_outlines array.")


def _build_prompts(
    *,
    expert_markdown: str,
    context: dict[str, Any],
) -> tuple[str, str]:
    """业务函数：处理 _build_prompts 对应的业务流程、校验或数据转换。"""
    system_prompt = "\n".join([
        expert_markdown,
        "",
        "你必须只输出可解析 JSON，不要输出 Markdown 或解释。",
        "JSON 顶层必须包含 series_story_plan、season_arc、continuity_ledger、episode_outlines。",
        "episode_outlines 每项必须包含 episode_number、title、hook、episode_goal、central_conflict、reversal、cliffhanger、previous_episode_handoff、next_episode_handoff、character_state_changes、foreshadowing_introduced、foreshadowing_resolved、character_ids、scene_ids。",
        "每集必须选择本集实际出现的 character_ids 和 scene_ids；不要把全系列资产池机械复制到每一集。",
        "如果本集需要新角色或新场景，请在 generated_assets.characters / generated_assets.scenes 中给出可创建资产的字段。",
        "asset_usage 用一句话说明每个角色或场景在本集中的剧情作用。",
    ])
    user_prompt = "\n".join([
        "请根据以下上下文生成整季故事规划。不要生成逐秒分镜。",
        json.dumps(context, ensure_ascii=False, indent=2),
    ])
    return system_prompt, user_prompt


async def generate_story_plan_with_expert(
    db: Session,
    *,
    series: Any,
    episodes: list[Any],
    character_ids: list[str],
    scene_ids: list[str],
    existing_artifacts: list[dict[str, Any]],
    runtime_config: dict[str, Any] | None = None,
    model_client: StoryModelClient | None = None,
    agent_runner: Any | None = None,
) -> StoryGeneratorResult:
    """业务函数：处理 generate_story_plan_with_expert 对应的业务流程、校验或数据转换。"""
    expert = get_expert(STORY_GENERATOR_EXPERT_ID)
    expert_markdown = read_expert_markdown(STORY_GENERATOR_EXPERT_ID)
    runtime_config = runtime_config or resolve_runtime_model_config(db, SCRIPT_GENERATION_SCENE)
    context = {
        "series": {
            "id": series.id,
            "title": series.title,
            "logline": series.logline,
            "total_episodes": int(series.total_episodes or 1),
            "story_bible_json": series.story_bible_json if isinstance(series.story_bible_json, dict) else {},
        },
        "episodes": [
            {
                "id": episode.id,
                "episode_number": int(episode.episode_number),
                "title": episode.title or f"Episode {episode.episode_number}",
            }
            for episode in episodes
        ],
        "character_ids": character_ids,
        "scene_ids": scene_ids,
        "series_asset_pool": {
            "characters": [
                {"id": character.id, "name": character.name, "role_type": character.role_type}
                for character in (series.characters or [])
            ],
            "scenes": [
                {"id": scene.id, "name": scene.name, "scene_type": scene.scene_type}
                for scene in (series.scenes or [])
            ],
        },
        "existing_approved_artifacts": existing_artifacts,
    }
    invocation = create_or_resume_invocation(
        db,
        idempotency_key=(
            f"storygen:{series.id}:{STORY_PLANNING_STAGE}:lead:{STORY_GENERATOR_EXPERT_ID}:{_context_hash(context)}"
        ),
        series_id=series.id,
        stage=STORY_PLANNING_STAGE,
        expert_id=STORY_GENERATOR_EXPERT_ID,
        role="lead",
        source=_source(STORY_GENERATOR_EXPERT_ID),
        input_summary={
            "series_id": series.id,
            "episode_count": len(episodes),
            "character_ids": character_ids,
            "scene_ids": scene_ids,
            "scene_key": SCRIPT_GENERATION_SCENE,
        },
    )
    started = time.monotonic()
    response_format = _response_format(runtime_config)
    system_prompt, user_prompt = _build_prompts(expert_markdown=expert_markdown, context=context)

    try:
        if model_client is not None:
            model_response = await model_client(system_prompt, user_prompt, runtime_config, response_format)
            raw_output, token_usage = _split_model_response(model_response)
            parsed = _parse_json_object(raw_output)
        else:
            parsed = await (agent_runner or LangChainAgentRunner()).run_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                runtime_config=runtime_config,
                tools=build_ai_video_tools(db, allowed_tools=["validate_json", "read_series_context"]),
            )
            raw_output = json.dumps(parsed, ensure_ascii=False)
            token_usage = parsed.get("token_usage", {}) if isinstance(parsed.get("token_usage"), dict) else {}
        _validate_story_payload(parsed)
    except httpx.TimeoutException as exc:
        error = AgencyRuntimeError("EXPERT_MODEL_TIMEOUT", "Story generator model call timed out.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except httpx.HTTPStatusError as exc:
        code = "EXPERT_MODEL_RATE_LIMITED" if exc.response.status_code == 429 else "EXPERT_MODEL_HTTP_ERROR"
        error = AgencyRuntimeError(code, f"Story generator model call failed with HTTP {exc.response.status_code}.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except httpx.RequestError as exc:
        error = AgencyRuntimeError("EXPERT_MODEL_HTTP_ERROR", "Story generator model request failed.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except openai.APITimeoutError as exc:
        error = AgencyRuntimeError("EXPERT_MODEL_TIMEOUT", "Story generator model call timed out.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except openai.RateLimitError as exc:
        error = AgencyRuntimeError("EXPERT_MODEL_RATE_LIMITED", "Story generator model call was rate limited.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except openai.APIStatusError as exc:
        code = "EXPERT_MODEL_RATE_LIMITED" if exc.response.status_code == 429 else "EXPERT_MODEL_HTTP_ERROR"
        error = AgencyRuntimeError(code, f"Story generator model call failed with HTTP {exc.response.status_code}.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except openai.APIConnectionError as exc:
        error = AgencyRuntimeError("EXPERT_MODEL_HTTP_ERROR", "Story generator model request failed.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except openai.APIError as exc:
        error = AgencyRuntimeError("EXPERT_MODEL_HTTP_ERROR", "Story generator model call failed.")
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc
    except AgencyRuntimeError as exc:
        _finalize_failed(db, invocation.id, exc, started)
        raise
    except Exception as exc:
        error = AgencyRuntimeError("EXPERT_RUNTIME_UNEXPECTED", str(exc))
        _finalize_failed(db, invocation.id, error, started)
        raise error from exc

    duration_ms = int((time.monotonic() - started) * 1000)
    finalized = finalize_invocation_and_audit(
        db,
        invocation_id=invocation.id,
        result_status="passed",
        output_summary={
            "summary": "故事规划生成完成",
            "generated_artifacts": {
                "series_story_plan": 1,
                "season_arc": 1,
                "continuity_ledger": 1 if isinstance(parsed.get("continuity_ledger"), dict) else 0,
                "episode_outlines": len(parsed.get("episode_outlines") or []),
            },
            "scene_key": SCRIPT_GENERATION_SCENE,
        },
        evidence=[
            {
                "series_id": series.id,
                "episode_count": len(parsed.get("episode_outlines") or []),
                "expert_id": STORY_GENERATOR_EXPERT_ID,
            }
        ],
        token_usage=token_usage,
        model_config_snapshot=redact_runtime_model_config(runtime_config),
        duration_ms=duration_ms,
    )
    model_trace = {
        "stage": STORY_PLANNING_STAGE,
        "stage_status": "expert",
        "expert_id": STORY_GENERATOR_EXPERT_ID,
        "scene_key": SCRIPT_GENERATION_SCENE,
        "source_repo": load_manifest().source_repo,
        "source_commit": load_manifest().source_commit,
        "source_path": expert.source_path,
        "source_sha256": expert.sha256,
        "invocation_id": finalized.id,
        "token_usage": token_usage,
        "model_config_snapshot": redact_runtime_model_config(runtime_config),
        "raw_output_preview": raw_output[:1000],
    }
    return StoryGeneratorResult(parsed=parsed, source_type="ai", model_trace=model_trace)


def _finalize_failed(
    db: Session,
    invocation_id: str,
    error: AgencyRuntimeError,
    started: float,
) -> None:
    """业务函数：处理 _finalize_failed 对应的业务流程、校验或数据转换。"""
    finalize_invocation_and_audit(
        db,
        invocation_id=invocation_id,
        result_status="failed",
        output_summary={
            "summary": "故事规划生成失败",
            "scene_key": SCRIPT_GENERATION_SCENE,
        },
        evidence=[],
        token_usage={},
        model_config_snapshot={},
        error_code=error.error_code,
        error_message=str(error),
        duration_ms=int((time.monotonic() - started) * 1000),
    )
