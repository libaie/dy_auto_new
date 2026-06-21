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
    allowed_tools = STAGE_TOOLS.get(job_stage)
    if allowed_tools is None:
        raise ValueError(f"Unsupported provider agent stage: {job_stage}")

    runner = agent_runner or LangChainAgentRunner()
    return await runner.run_json(
        system_prompt=(
            "You are an AI video provider stage operator. Use only the provided tools "
            "to submit and query provider work for this production job. "
            "Call each tool named in required_sequence in order with run_id and job_id, "
            "then return the final tool result as a JSON object."
        ),
        user_prompt=json.dumps(
            {
                "run_id": run_id,
                "job_id": job_id,
                "job_stage": job_stage,
                "required_sequence": allowed_tools,
            },
            ensure_ascii=False,
        ),
        runtime_config=runtime_config,
        tools=build_ai_video_tools(db, allowed_tools=allowed_tools),
    )
