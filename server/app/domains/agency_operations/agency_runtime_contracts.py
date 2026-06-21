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
