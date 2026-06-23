"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 provider_stage_orchestrator 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.domains.ai_video_series.langchain_runtime.agent_runner import LangChainAgentRunner
from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools


STAGE_TOOLS = {
    "image_generation": ["submit_image_generation", "query_image_task"],
    "video_generation": ["submit_video_generation", "query_video_task"],
    "episode_compose": ["submit_compose", "query_compose_task"],
    "composition": ["submit_compose", "query_compose_task"],
}


async def run_provider_stage_agent(
    db: Session | None,
    *,
    run_id: str,
    job_id: str,
    job_stage: str,
    runtime_config: dict[str, Any],
    agent_runner: LangChainAgentRunner | None = None,
) -> dict[str, Any]:
    """业务函数：处理 run_provider_stage_agent 对应的业务流程、校验或数据转换。

    入参：db、run_id、job_id、job_stage、runtime_config、agent_runner 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    allowed_tools = STAGE_TOOLS.get(job_stage)
    if allowed_tools is None:
        raise ValueError(f"Unsupported provider agent stage: {job_stage}")

    if agent_runner is None and str((runtime_config or {}).get("provider") or "").lower() in {"mock", "test"}:
        return await _run_provider_tools_directly(db, allowed_tools=allowed_tools, run_id=run_id, job_id=job_id)

    runner = agent_runner or LangChainAgentRunner()
    return await runner.run_json(
        system_prompt=(
            "You are an AI video provider stage operator. Use only the provided tools "
            "to submit and query provider work for this production job. "
            "Call the submit tool first with run_id and job_id. If the submit result is "
            "successful and already includes assets, return it. Otherwise call the matching "
            "query tool and return that final tool result as a JSON object."
        ),
        user_prompt=json.dumps(
            {
                "run_id": run_id,
                "job_id": job_id,
                "job_stage": job_stage,
                "allowed_tools": allowed_tools,
            },
            ensure_ascii=False,
        ),
        runtime_config=runtime_config,
        tools=build_ai_video_tools(db, allowed_tools=allowed_tools),
    )


async def _run_provider_tools_directly(
    db: Session | None,
    *,
    allowed_tools: list[str],
    run_id: str,
    job_id: str,
) -> dict[str, Any]:
    """业务函数：处理 _run_provider_tools_directly 对应的业务流程、校验或数据转换。

    入参：db、allowed_tools、run_id、job_id 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    tools = {tool.name: tool for tool in build_ai_video_tools(db, allowed_tools=allowed_tools)}
    for name in allowed_tools:
        result = await tools[name].ainvoke({"run_id": run_id, "job_id": job_id})
        if result.get("status") != "success" or int(result.get("asset_count") or 0) > 0:
            return result
    return result
