from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import httpx

from app.domains.agency_operations.agency_runtime_contracts import (
    AgencyRuntimeError,
    OPENAI_CHAT_COMPLETIONS_PROTOCOL,
    OPENAI_COMPATIBLE_PROVIDERS,
    runtime_setting,
)
from app.domains.agency_operations.agency_manifest import (
    get_expert,
    read_expert_markdown,
)
from app.domains.agency_operations.agency_prompting import build_expert_prompt
from app.domains.agency_operations.agency_scorecard_contracts import normalize_scorecard
from app.domains.model_configuration.runtime_model_config import redact_runtime_model_config


VALID_RESULT_STATUSES = {"passed", "warn", "blocked", "failed"}
REQUIRED_OUTPUT_FIELDS = {
    "decision": str,
    "findings": list,
    "recommendations": list,
    "required_changes": list,
    "evidence": list,
}
SECRET_KEYS = {
    "accesstoken",
    "apikey",
    "apisecret",
    "authorization",
    "bearertoken",
    "clientsecret",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "secretkey",
    "token",
    "xapikey",
}
SECRET_STRING_MARKERS = (
    "authorization",
    "bearer",
    "api_key",
    "api key",
    "system prompt",
    "user prompt",
    "full prompt",
    "dy_auto system safety rules",
    "expert markdown begins",
)
MIN_SECRET_VALUE_LENGTH = 4


@dataclass(frozen=True)
class AgencyRuntimeResult:
    result_status: str
    output_summary: dict[str, Any]
    evidence: list[Any]
    token_usage: dict[str, Any]
    model_config_snapshot: dict[str, Any]


MessageContent = str | list[dict[str, Any]]
ModelClientResponse = str | dict[str, Any]
ModelClient = Callable[[str, MessageContent, dict[str, Any]], Awaitable[ModelClientResponse]]
_runtime_setting = runtime_setting


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _collect_secret_values(value: Any) -> set[str]:
    secrets: set[str] = set()

    if isinstance(value, dict):
        for key, item in value.items():
            key_is_secret = isinstance(key, str) and _normalize_key(key) in SECRET_KEYS
            if key_is_secret and isinstance(item, str):
                secret = item.strip()
                if len(secret) >= MIN_SECRET_VALUE_LENGTH:
                    secrets.add(secret)
            secrets.update(_collect_secret_values(item))
    elif isinstance(value, list):
        for item in value:
            secrets.update(_collect_secret_values(item))

    return secrets


def _redact_secrets(value: Any, secret_values: set[str] | None = None) -> Any:
    secret_values = secret_values or set()
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if isinstance(key, str) and _normalize_key(key) in SECRET_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_secrets(item, secret_values)
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item, secret_values) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_STRING_MARKERS):
            return "[REDACTED]"
        redacted_value = value
        for secret in sorted(secret_values, key=len, reverse=True):
            redacted_value = redacted_value.replace(secret, "[REDACTED]")
        return redacted_value
    return value


def _chat_completion_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def _ensure_openai_compatible_provider(config: dict[str, Any]) -> None:
    protocol = _runtime_setting(config, "protocol", "")
    if isinstance(protocol, str) and protocol.lower() == OPENAI_CHAT_COMPLETIONS_PROTOCOL:
        return

    provider = config.get("provider", "")
    if isinstance(provider, str) and provider.lower() in OPENAI_COMPATIBLE_PROVIDERS:
        return

    raise AgencyRuntimeError(
        "EXPERT_MODEL_PROVIDER_UNSUPPORTED",
        "Agency expert runtime only supports OpenAI-compatible chat completion providers.",
    )


async def _default_model_client(
    system_prompt: str,
    user_prompt: MessageContent,
    config: dict[str, Any],
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> ModelClientResponse:
    _ensure_openai_compatible_provider(config)

    base_url = (config.get("base_url") or "").strip()
    api_key = config.get("api_key") or ""
    model = config.get("model") or config.get("model_id") or ""
    if not base_url or not api_key or not model:
        raise AgencyRuntimeError(
            "EXPERT_MODEL_CONFIG_MISSING",
            "Agency expert runtime model requires base_url, api_key, and model.",
        )

    timeout = float(_runtime_setting(config, "timeout", 60))
    max_tokens = int(_runtime_setting(config, "max_tokens", 2048))
    temperature = float(_runtime_setting(config, "temperature", 0.2))

    client_kwargs: dict[str, Any] = {"timeout": timeout}
    if http_transport is not None:
        client_kwargs["transport"] = http_transport

    async with httpx.AsyncClient(**client_kwargs) as client:
        response = await client.post(
            _chat_completion_url(base_url),
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise AgencyRuntimeError(
                "EXPERT_MODEL_HTTP_ERROR",
                "Agency expert model response was not valid JSON.",
            ) from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AgencyRuntimeError(
            "EXPERT_MODEL_HTTP_ERROR",
            "Agency expert model response did not include chat completion content.",
        ) from exc
    if not isinstance(content, str):
        raise AgencyRuntimeError(
            "EXPERT_MODEL_HTTP_ERROR",
            "Agency expert model response chat completion content was not a string.",
        )
    return {"content": content, "token_usage": data.get("usage", {})}


def _split_model_response(response: ModelClientResponse) -> tuple[str, dict[str, Any]]:
    if isinstance(response, str):
        return response, {}
    if isinstance(response, dict):
        content = response.get("content")
        token_usage = response.get("token_usage") or {}
        if isinstance(content, str) and isinstance(token_usage, dict):
            return content, token_usage
    raise AgencyRuntimeError(
        "EXPERT_OUTPUT_INVALID_JSON",
        "Agency expert model response must be JSON content.",
    )


def _load_expert_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", raw or ""):
            try:
                parsed, _ = decoder.raw_decode(raw[match.start():])
            except json.JSONDecodeError:
                continue
            return parsed
    raise AgencyRuntimeError(
        "EXPERT_OUTPUT_INVALID_JSON",
        "Agency expert output is not valid JSON.",
    )


def _parse_expert_output(raw: str) -> dict[str, Any]:
    parsed = _load_expert_json(raw)
    if not isinstance(parsed, dict):
        raise AgencyRuntimeError(
            "EXPERT_OUTPUT_INVALID_JSON",
            "Agency expert output must be a JSON object.",
        )
    status = parsed.get("status")
    if status not in VALID_RESULT_STATUSES:
        raise AgencyRuntimeError(
            "EXPERT_OUTPUT_INVALID_JSON",
            "Agency expert output status is not allowed.",
        )
    for field, expected_type in REQUIRED_OUTPUT_FIELDS.items():
        if not isinstance(parsed.get(field), expected_type):
            raise AgencyRuntimeError(
                "EXPERT_OUTPUT_INVALID_JSON",
                f"Agency expert output field {field} has invalid type.",
            )
    return parsed


class AgencySkillRuntime:
    def __init__(
        self,
        model_client: ModelClient | None = None,
        http_transport: httpx.AsyncBaseTransport | None = None,
    ):
        if model_client is not None:
            self.model_client = model_client
        else:
            async def default_client(
                system_prompt: str,
                user_prompt: MessageContent,
                config: dict[str, Any],
            ) -> ModelClientResponse:
                return await _default_model_client(
                    system_prompt,
                    user_prompt,
                    config,
                    http_transport=http_transport,
                )

            self.model_client = default_client

    async def invoke(
        self,
        *,
        db,
        expert_id: str,
        stage: str,
        role: str,
        stage_context: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> AgencyRuntimeResult:
        _ = db
        get_expert(expert_id)
        expert_markdown = read_expert_markdown(expert_id)
        output_schema = {
            "type": "object",
            "required": [
                "status",
                "decision",
                "findings",
                "recommendations",
                "required_changes",
                "evidence",
            ],
            "properties": {
                "status": {"enum": sorted(VALID_RESULT_STATUSES)},
                "decision": {"type": "string"},
                "findings": {"type": "array"},
                "recommendations": {"type": "array"},
                "required_changes": {"type": "array"},
                "evidence": {"type": "array"},
                "creative_patches": {"type": "array"},
                "scorecard": {"type": "object"},
            },
        }
        prompt = build_expert_prompt(
            expert_id=expert_id,
            expert_markdown=expert_markdown,
            stage=stage,
            role=role,
            stage_context=stage_context,
            output_schema=output_schema,
        )

        try:
            model_response = await self.model_client(
                prompt.system_prompt,
                prompt.user_prompt,
                runtime_config,
            )
        except httpx.TimeoutException as exc:
            raise AgencyRuntimeError("EXPERT_MODEL_TIMEOUT", "Agency expert model call timed out.") from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_code = "EXPERT_MODEL_RATE_LIMITED" if status_code == 429 else "EXPERT_MODEL_HTTP_ERROR"
            raise AgencyRuntimeError(
                error_code,
                f"Agency expert model call failed with HTTP {status_code}.",
            ) from exc
        except httpx.RequestError as exc:
            raise AgencyRuntimeError("EXPERT_MODEL_HTTP_ERROR", "Agency expert model request failed.") from exc

        raw, response_token_usage = _split_model_response(model_response)
        parsed = _parse_expert_output(raw)
        token_usage = parsed.get("token_usage")
        if not isinstance(token_usage, dict):
            token_usage = response_token_usage
        secret_values = _collect_secret_values(runtime_config)

        output_summary = {
            "decision": _redact_secrets(parsed["decision"], secret_values),
            "findings": _redact_secrets(parsed["findings"], secret_values),
            "recommendations": _redact_secrets(parsed["recommendations"], secret_values),
            "required_changes": _redact_secrets(parsed["required_changes"], secret_values),
        }
        if isinstance(parsed.get("creative_patches"), list):
            output_summary["creative_patches"] = _redact_secrets(parsed["creative_patches"], secret_values)
        if isinstance(parsed.get("scorecard"), dict):
            output_summary["scorecard"] = _redact_secrets(normalize_scorecard(parsed["scorecard"]), secret_values)

        return AgencyRuntimeResult(
            result_status=parsed["status"],
            output_summary=output_summary,
            evidence=_redact_secrets(parsed["evidence"], secret_values),
            token_usage=token_usage,
            model_config_snapshot=_redact_secrets(redact_runtime_model_config(runtime_config), secret_values),
        )
