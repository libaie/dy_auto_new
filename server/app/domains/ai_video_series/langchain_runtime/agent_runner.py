from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Callable

from langchain.agents import create_agent

from app.domains.agency_operations.agency_runtime_contracts import AgencyRuntimeError
from app.domains.ai_video_series.langchain_runtime.models import create_chat_model


def extract_json_object(raw: Any) -> dict[str, Any]:
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
    def __init__(self, agent_factory: Callable[..., Any] | None = None):
        self.agent_factory = agent_factory or create_agent

    async def run_json(
        self,
        *,
        system_prompt: str,
        user_prompt: Any,
        runtime_config: dict[str, Any],
        tools: list[Any],
    ) -> dict[str, Any]:
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
