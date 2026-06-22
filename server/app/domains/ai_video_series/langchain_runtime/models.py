"""AI 视频系列业务域模块。

AI 视频系列业务域，负责系列策划、风格锁定、剧集资产范围和 LangChain 工具编排。本文件负责 models 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from app.domains.agency_operations.agency_runtime_contracts import (
    AgencyRuntimeError,
    OPENAI_CHAT_COMPLETIONS_PROTOCOL,
    OPENAI_COMPATIBLE_PROVIDERS,
    runtime_setting,
)


def ensure_langchain_provider_supported(config: dict[str, Any]) -> None:
    """业务函数：处理 ensure_langchain_provider_supported 对应的业务流程、校验或数据转换。

    入参：config 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    protocol = str(runtime_setting(config, "protocol", "") or "").lower()
    provider = str(config.get("provider") or "").lower()
    if protocol == OPENAI_CHAT_COMPLETIONS_PROTOCOL or provider in OPENAI_COMPATIBLE_PROVIDERS:
        return
    raise AgencyRuntimeError(
        "EXPERT_MODEL_PROVIDER_UNSUPPORTED",
        "AI video LangChain runtime only supports OpenAI-compatible chat completion providers.",
    )


def build_langchain_openai_kwargs(config: dict[str, Any]) -> dict[str, Any]:
    """业务函数：处理 build_langchain_openai_kwargs 对应的业务流程、校验或数据转换。

    入参：config 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    ensure_langchain_provider_supported(config)
    base_url = str(config.get("base_url") or "").strip()
    api_key = str(config.get("api_key") or "").strip()
    model = str(config.get("model") or config.get("model_id") or "").strip()
    missing = [name for name, value in (("base_url", base_url), ("api_key", api_key), ("model", model)) if not value]
    if missing:
        raise AgencyRuntimeError(
            "EXPERT_MODEL_CONFIG_MISSING",
            f"AI video LangChain runtime requires {', '.join(missing)}.",
        )
    return {
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": float(runtime_setting(config, "temperature", 0.2)),
        "max_tokens": int(runtime_setting(config, "max_tokens", 2048)),
        "timeout": float(runtime_setting(config, "timeout", 60)),
    }


def create_chat_model(config: dict[str, Any]) -> ChatOpenAI:
    """业务函数：处理 create_chat_model 对应的业务流程、校验或数据转换。

    入参：config 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return ChatOpenAI(**build_langchain_openai_kwargs(config))
