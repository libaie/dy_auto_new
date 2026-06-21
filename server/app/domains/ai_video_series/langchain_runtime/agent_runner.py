"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 agent_runner 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Callable

from langchain.agents import create_agent

from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.models import create_chat_model


def extract_json_object(raw: Any) -> dict[str, Any]:
    """业务函数：处理 extract_json_object 对应的业务流程、校验或数据转换。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "LangChain agent output was empty.")
    candidates = [raw.strip()]
    if "```" in raw:
        for part in raw.split("```"):
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate:
                candidates.append(candidate)
    decoder = json.JSONDecoder()
    embedded_candidates = []
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, JSONDecodeError):
            embedded_candidates.append(candidate)
            continue
        if isinstance(parsed, dict):
            return parsed
        raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "LangChain agent output was not a JSON object.")
    for candidate in embedded_candidates:
        if candidate.lstrip().startswith("["):
            continue
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[index:])
            except JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise AgencyRuntimeError("EXPERT_OUTPUT_INVALID_JSON", "LangChain agent output was not valid JSON.")


def _content_from_agent_response(response: Any) -> Any:
    """业务函数：处理 _content_from_agent_response 对应的业务流程、校验或数据转换。"""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                return last.get("content")
            content = getattr(last, "content", None)
            if content is not None:
                return content
        return response.get("content", response)
    content = getattr(response, "content", None)
    return content if content is not None else response


class LangChainAgentRunner:
    """业务类：承载 LangChainAgentRunner 相关的数据结构、状态或业务协作。"""
    def __init__(self, agent_factory: Callable[..., Any] | None = None):
        """初始化业务对象依赖，保存后续流程需要的运行上下文。"""
        self.agent_factory = agent_factory or create_agent

    async def run_json(
        self,
        *,
        system_prompt: str,
        user_prompt: Any,
        runtime_config: dict[str, Any],
        tools: list[Any],
    ) -> dict[str, Any]:
        """业务函数：处理 run_json 对应的业务流程、校验或数据转换。"""
        model = None if self.agent_factory is not create_agent else create_chat_model(runtime_config)
        agent = self.agent_factory(model=model, tools=tools)
        response = await agent.ainvoke(
            {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            }
        )
        return extract_json_object(_content_from_agent_response(response))


async def run_structured_ai_video_json(
    *,
    system_prompt: str,
    user_prompt: Any,
    runtime_config: dict[str, Any],
    db: Any = None,
    allowed_tools: list[str] | None = None,
) -> dict[str, Any]:
    """业务函数：处理 run_structured_ai_video_json 对应的业务流程、校验或数据转换。"""
    from app.domains.ai_video_series.langchain_runtime.tools import build_ai_video_tools

    return await LangChainAgentRunner().run_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        runtime_config=runtime_config,
        tools=build_ai_video_tools(db, allowed_tools=allowed_tools or ["validate_json"]),
    )
