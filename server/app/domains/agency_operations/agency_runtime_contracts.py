"""专家团队运营业务域模块。

专家团队运营业务域，负责多智能体专家审查、创意补丁、返修闭环和审计持久化。本文件负责 agency_runtime_contracts 相关业务规则、状态转换和外部系统边界。
"""

from __future__ import annotations

from typing import Any

OPENAI_COMPATIBLE_PROVIDERS = {"openai", "ark", "doubao", "openai-compatible", "bailian"}
OPENAI_CHAT_COMPLETIONS_PROTOCOL = "openai_chat_completions"


class AgencyRuntimeError(RuntimeError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


def runtime_setting(config: dict[str, Any], key: str, default: Any) -> Any:
    nested = config.get("config")
    if isinstance(nested, dict) and key in nested:
        return nested[key]
    return config.get(key, default)
