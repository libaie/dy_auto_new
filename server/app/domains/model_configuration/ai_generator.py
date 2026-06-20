"""AI content generation service -- calls external LLM API with sensitive word filtering."""
import json
import logging
from typing import Any

import httpx

from app.config import AI_MAX_RETRIES
from app.domains.content_collection.content_service import content_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个抖音评论/私信内容生成助手。根据给定的模板和上下文，生成自然、友好的中文内容。
规则：
1. 保持内容自然，像真人写的
2. 不要包含广告、链接、联系方式
3. 不要包含敏感、违规、政治相关内容
4. 内容长度控制在 20-100 字
5. 直接输出生成的内容，不要加引号或解释"""


class AiGeneratorService:
    """Generates content via external LLM API with sensitive word filtering.

    Supports two providers via AI_PROVIDER config:
    - "anthropic": Uses Anthropic Messages API (x-api-key header, /v1/messages)
    - "openai": Uses OpenAI-compatible API (Authorization Bearer, /v1/chat/completions)
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init httpx client with separated connect/read timeouts."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
            )
        return self._client

    async def aclose(self):
        """Close the httpx client. Call during app shutdown."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate(
        self,
        db,
        template_body: str,
        context: dict[str, Any],
    ) -> str:
        """Generate content from template + context. Retries if sensitive words detected.

        Args:
            db: SQLAlchemy session (for sensitive word lookup and config)
            template_body: Template text with {variable} placeholders already substituted
            context: Additional context for the AI prompt

        Returns:
            Generated content string

        Raises:
            RuntimeError: If AI API is not configured or all retries fail
            ValueError: If all retries produce sensitive content
        """
        from app.config import get_ai_config_with_key
        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured. Set AI_API_KEY env var or save in Settings page.")

        user_prompt = self._build_prompt(template_body, context)

        for attempt in range(AI_MAX_RETRIES):
            try:
                content = await self._call_api(ai_cfg, user_prompt)
            except httpx.HTTPError as e:
                logger.warning("AI API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(f"AI API failed after {AI_MAX_RETRIES} attempts: {e}") from e
                continue

            if db and content_service.contains_sensitive(db, content):
                logger.info("Generated content contains sensitive words, retrying (%d/%d)", attempt + 1, AI_MAX_RETRIES)
                if attempt == AI_MAX_RETRIES - 1:
                    raise ValueError("All generated content contained sensitive words after max retries")
                continue

            return content

    async def generate_custom_stream(
        self, db, system_prompt: str, user_prompt: str,
        max_tokens: int = 4096, temperature: float = 0.7,
    ):
        """Generate content with streaming — yields text chunks as they arrive from the AI API.
        Only supports OpenAI-compatible streaming (DeepSeek, OpenAI, etc.).
        Anthropic streaming not yet implemented.
        """
        from app.config import get_ai_config_with_key
        ai_cfg = get_ai_config_with_key(db)
        async for chunk in self.generate_custom_stream_with_config(
            ai_cfg,
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk

    async def generate_custom_stream_with_config(
        self,
        ai_cfg: dict,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """Generate streaming content from a pre-resolved AI config.

        This helper intentionally does not accept a DB session so streaming
        responses do not keep SQLAlchemy sessions open while waiting on the LLM.
        """
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")

        api_url = ai_cfg.get("api_url", "")
        if "/v1/messages" in api_url:
            raise RuntimeError("Streaming is only supported for OpenAI-compatible APIs")

        client = self._get_client()
        attempts = max(1, AI_MAX_RETRIES)
        stream_started = False

        for attempt in range(attempts):
            try:
                async with client.stream(
                    "POST",
                    api_url,
                    headers={
                        "Authorization": f"Bearer {ai_cfg['api_key']}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": ai_cfg.get("model", "deepseek-chat"),
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": True,
                        **({} if not ai_cfg.get("thinking_enabled") else {"thinking": {"type": "enabled"}}),
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                stream_started = True
                                yield content
                        except json.JSONDecodeError:
                            continue
                    return  # stream completed
            except httpx.HTTPError as e:
                logger.warning(
                    "generate_custom_stream_with_config API call failed (attempt %d/%d): %s",
                    attempt + 1, attempts, e,
                )
                if stream_started:
                    raise RuntimeError(
                        f"generate_custom_stream_with_config failed after streaming started: {e}"
                    ) from e
                if attempt == attempts - 1:
                    raise RuntimeError(
                        f"generate_custom_stream_with_config failed after {attempts} attempts: {e}"
                    ) from e
                continue

    async def generate_custom(
        self, db, system_prompt: str, user_prompt: str,
        max_tokens: int = 4096, temperature: float = 0.7,
        thinking_enabled: bool = None,
        request_timeout_seconds: float | None = None,
    ) -> str:
        """Generate content with custom system prompt and parameters. No sensitive word filtering.

        Args:
            thinking_enabled: If not None, overrides the global AI thinking config.
        """
        from app.config import get_ai_config_with_key, AI_MAX_RETRIES
        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")

        use_thinking = ai_cfg.get("thinking_enabled") if thinking_enabled is None else thinking_enabled

        api_url = ai_cfg.get("api_url", "")
        client = self._get_client()
        is_anthropic = "/v1/messages" in api_url
        request_timeout = (
            httpx.Timeout(connect=5.0, read=float(request_timeout_seconds), write=10.0, pool=5.0)
            if request_timeout_seconds is not None else None
        )

        for attempt in range(max(1, AI_MAX_RETRIES)):
            try:
                if is_anthropic:
                    base_url = api_url.rstrip("/").rsplit("/v1/messages", 1)[0]
                    request_kwargs = {}
                    if request_timeout is not None:
                        request_kwargs["timeout"] = request_timeout
                    response = await client.post(
                        f"{base_url}/v1/messages",
                        headers={
                            "x-api-key": ai_cfg["api_key"],
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": ai_cfg.get("model", "claude-3-haiku-20240307"),
                            "max_tokens": max_tokens,
                            **({} if not use_thinking else {"thinking": {"type": "enabled", "budget_tokens": ai_cfg.get("thinking_budget", 8192)}}),
                            "system": system_prompt,
                            "messages": [{"role": "user", "content": user_prompt}],
                        },
                        **request_kwargs,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["content"][0]["text"].strip()
                else:
                    request_kwargs = {}
                    if request_timeout is not None:
                        request_kwargs["timeout"] = request_timeout
                    response = await client.post(
                        api_url,
                        headers={
                            "Authorization": f"Bearer {ai_cfg['api_key']}",
                            "content-type": "application/json",
                        },
                        json={
                            "model": ai_cfg.get("model", "deepseek-chat"),
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            **({} if not use_thinking else {"thinking": {"type": "enabled"}}),
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        },
                        **request_kwargs,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPError as e:
                logger.warning("generate_custom API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(f"generate_custom failed after {AI_MAX_RETRIES} attempts: {e}") from e
                continue

    async def _call_api(self, cfg: dict, user_prompt: str) -> str:
        """Call the AI API and return the generated text. Dispatches by provider."""
        api_url = cfg.get("api_url", "")
        # Anthropic uses /v1/messages; OpenAI-compatible uses /v1/chat/completions
        if "/v1/messages" in api_url:
            return await self._call_anthropic(cfg, user_prompt)
        return await self._call_openai(cfg, user_prompt)

    async def _call_anthropic(self, cfg: dict, user_prompt: str) -> str:
        """Call Anthropic Messages API."""
        client = self._get_client()
        base_url = cfg["api_url"].rstrip("/").rsplit("/v1/messages", 1)[0]
        response = await client.post(
            f"{base_url}/v1/messages",
            headers={
                "x-api-key": cfg["api_key"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": cfg.get("model", "claude-3-haiku-20240307"),
                "max_tokens": 512,
                **({} if not cfg.get("thinking_enabled") else {"thinking": {"type": "enabled", "budget_tokens": cfg.get("thinking_budget", 8192)}}),
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"].strip()

    async def _call_openai(self, cfg: dict, user_prompt: str) -> str:
        """Call OpenAI-compatible Chat Completions API."""
        client = self._get_client()
        response = await client.post(
            cfg["api_url"],
            headers={
                "Authorization": f"Bearer {cfg['api_key']}",
                "content-type": "application/json",
            },
            json={
                "model": cfg.get("model", "deepseek-chat"),
                "max_tokens": 512,
                **({} if not cfg.get("thinking_enabled") else {"thinking": {"type": "enabled"}}),
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _build_prompt(template_body: str, context: dict[str, Any]) -> str:
        """Build the user prompt from template and context.

        Dynamically includes all context keys that have values,
        rather than hardcoding specific field names.
        """
        parts = [f"模板内容：{template_body}"]

        # Dynamic context — include all non-empty string values
        key_labels = {
            "keyword": "搜索关键词",
            "username": "目标用户",
            "video_title": "视频标题",
        }
        for key, value in context.items():
            if isinstance(value, str) and value:
                label = key_labels.get(key, key)
                parts.append(f"{label}：{value}")

        parts.append("请根据以上信息生成一条自然的评论/私信内容。只输出内容本身。")
        return "\n".join(parts)


ai_generator = AiGeneratorService()
