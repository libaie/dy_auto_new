"""AI content generation service -- calls external LLM API with sensitive word filtering."""
import logging
from typing import Any

import httpx

from app.config import AI_API_KEY, AI_BASE_URL, AI_MODEL, AI_PROVIDER, AI_MAX_RETRIES
from app.services.content_service import content_service

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
            db: SQLAlchemy session (for sensitive word lookup)
            template_body: Template text with {variable} placeholders already substituted
            context: Additional context for the AI prompt

        Returns:
            Generated content string

        Raises:
            RuntimeError: If AI API is not configured or all retries fail
            ValueError: If all retries produce sensitive content
        """
        if not AI_API_KEY:
            raise RuntimeError("AI_API_KEY not configured. Set the environment variable.")

        user_prompt = self._build_prompt(template_body, context)

        for attempt in range(AI_MAX_RETRIES):
            try:
                content = await self._call_api(user_prompt)
            except httpx.HTTPError as e:
                logger.warning("AI API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == AI_MAX_RETRIES - 1:
                    raise RuntimeError(f"AI API failed after {AI_MAX_RETRIES} attempts: {e}") from e
                continue

            if content_service.contains_sensitive(db, content):
                logger.info("Generated content contains sensitive words, retrying (%d/%d)", attempt + 1, AI_MAX_RETRIES)
                if attempt == AI_MAX_RETRIES - 1:
                    raise ValueError("All generated content contained sensitive words after max retries")
                continue

            return content

    async def _call_api(self, user_prompt: str) -> str:
        """Call the AI API and return the generated text. Dispatches by AI_PROVIDER."""
        if AI_PROVIDER == "openai":
            return await self._call_openai(user_prompt)
        return await self._call_anthropic(user_prompt)

    async def _call_anthropic(self, user_prompt: str) -> str:
        """Call Anthropic Messages API."""
        client = self._get_client()
        response = await client.post(
            f"{AI_BASE_URL.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": AI_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "max_tokens": 200,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"].strip()

    async def _call_openai(self, user_prompt: str) -> str:
        """Call OpenAI-compatible Chat Completions API."""
        client = self._get_client()
        response = await client.post(
            f"{AI_BASE_URL.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "content-type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "max_tokens": 200,
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
        """Build the user prompt from template and context."""
        parts = [f"模板内容：{template_body}"]
        if context.get("keyword"):
            parts.append(f"搜索关键词：{context['keyword']}")
        if context.get("username"):
            parts.append(f"目标用户：{context['username']}")
        if context.get("video_title"):
            parts.append(f"视频标题：{context['video_title']}")
        parts.append("请根据以上信息生成一条自然的评论/私信内容。只输出内容本身。")
        return "\n".join(parts)


ai_generator = AiGeneratorService()
