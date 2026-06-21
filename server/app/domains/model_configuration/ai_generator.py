"""AI content generation service -- LangChain-backed LLM calls with sensitive word filtering."""
import logging
from typing import Any

from langchain_openai import ChatOpenAI

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
    """Generates content through LangChain while preserving the legacy service API."""

    async def aclose(self):
        """Kept for app shutdown compatibility; LangChain models are per-call."""
        return None

    async def generate(
        self,
        db,
        template_body: str,
        context: dict[str, Any],
    ) -> str:
        from app.config import get_ai_config_with_key

        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured. Set AI_API_KEY env var or save in Settings page.")
        self._ensure_openai_compatible(ai_cfg)

        user_prompt = self._build_prompt(template_body, context)
        for attempt in range(max(1, AI_MAX_RETRIES)):
            try:
                content = await self._call_api(ai_cfg, user_prompt)
            except Exception as e:
                logger.warning("AI API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == max(1, AI_MAX_RETRIES) - 1:
                    raise RuntimeError(f"AI API failed after {max(1, AI_MAX_RETRIES)} attempts: {e}") from e
                continue

            if db and content_service.contains_sensitive(db, content):
                logger.info("Generated content contains sensitive words, retrying (%d/%d)", attempt + 1, AI_MAX_RETRIES)
                if attempt == max(1, AI_MAX_RETRIES) - 1:
                    raise ValueError("All generated content contained sensitive words after max retries")
                continue

            return content
        raise RuntimeError("AI API failed")

    async def generate_custom_stream(
        self, db, system_prompt: str, user_prompt: str,
        max_tokens: int = 4096, temperature: float = 0.7,
    ):
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
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")
        self._ensure_openai_compatible(ai_cfg)

        attempts = max(1, AI_MAX_RETRIES)
        stream_started = False
        for attempt in range(attempts):
            try:
                model = self._create_chat_model(
                    ai_cfg,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    thinking_enabled=ai_cfg.get("thinking_enabled"),
                )
                async for chunk in model.astream([("system", system_prompt), ("human", user_prompt)]):
                    text = self._message_text(chunk, strip=False)
                    if text:
                        stream_started = True
                        yield text
                return
            except Exception as e:
                logger.warning(
                    "generate_custom_stream_with_config API call failed (attempt %d/%d): %s",
                    attempt + 1,
                    attempts,
                    e,
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
        from app.config import get_ai_config_with_key

        ai_cfg = get_ai_config_with_key(db)
        if not ai_cfg or not ai_cfg.get("api_key"):
            raise RuntimeError("AI API not configured")
        self._ensure_openai_compatible(ai_cfg)

        for attempt in range(max(1, AI_MAX_RETRIES)):
            try:
                model = self._create_chat_model(
                    ai_cfg,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    thinking_enabled=ai_cfg.get("thinking_enabled") if thinking_enabled is None else thinking_enabled,
                    request_timeout_seconds=request_timeout_seconds,
                )
                response = await model.ainvoke([("system", system_prompt), ("human", user_prompt)])
                return self._message_text(response)
            except Exception as e:
                logger.warning("generate_custom API call failed (attempt %d/%d): %s", attempt + 1, AI_MAX_RETRIES, e)
                if attempt == max(1, AI_MAX_RETRIES) - 1:
                    raise RuntimeError(f"generate_custom failed after {max(1, AI_MAX_RETRIES)} attempts: {e}") from e
                continue
        raise RuntimeError("generate_custom failed")

    async def _call_api(self, cfg: dict, user_prompt: str) -> str:
        self._ensure_openai_compatible(cfg)
        return await self._call_openai(cfg, user_prompt)

    async def _call_anthropic(self, cfg: dict, user_prompt: str) -> str:
        raise RuntimeError("LangChain AI generator only supports OpenAI-compatible APIs")

    async def _call_openai(self, cfg: dict, user_prompt: str) -> str:
        model = self._create_chat_model(
            cfg,
            max_tokens=512,
            temperature=float(cfg.get("temperature", 0.7)),
            thinking_enabled=cfg.get("thinking_enabled"),
        )
        response = await model.ainvoke([("system", SYSTEM_PROMPT), ("human", user_prompt)])
        return self._message_text(response)

    def _create_chat_model(
        self,
        cfg: dict,
        *,
        max_tokens: int,
        temperature: float,
        thinking_enabled: bool | None = None,
        request_timeout_seconds: float | None = None,
    ) -> ChatOpenAI:
        return ChatOpenAI(**self._langchain_kwargs(
            cfg,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking_enabled=thinking_enabled,
            request_timeout_seconds=request_timeout_seconds,
        ))

    @classmethod
    def _langchain_kwargs(
        cls,
        cfg: dict,
        *,
        max_tokens: int,
        temperature: float,
        thinking_enabled: bool | None = None,
        request_timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        api_key = str((cfg or {}).get("api_key") or "").strip()
        model = str((cfg or {}).get("model") or "deepseek-chat").strip()
        base_url = cls._base_url_from_config(cfg or {})
        if not api_key or not base_url or not model:
            raise RuntimeError("AI API not configured")
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": float(request_timeout_seconds or cfg.get("timeout") or 60),
        }
        if thinking_enabled:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        return kwargs

    @staticmethod
    def _ensure_openai_compatible(cfg: dict) -> None:
        api_url = str((cfg or {}).get("api_url") or (cfg or {}).get("base_url") or "")
        if "/v1/messages" in api_url:
            raise RuntimeError("LangChain AI generator only supports OpenAI-compatible APIs")

    @classmethod
    def _base_url_from_config(cls, cfg: dict) -> str:
        api_url = str(cfg.get("api_url") or cfg.get("base_url") or "").strip().rstrip("/")
        if "/v1/messages" in api_url:
            raise RuntimeError("LangChain AI generator only supports OpenAI-compatible APIs")
        suffix = "/chat/completions"
        return api_url[:-len(suffix)] if api_url.endswith(suffix) else api_url

    @staticmethod
    def _message_text(message: Any, *, strip: bool = True) -> str:
        content = getattr(message, "content", message)
        if isinstance(content, list):
            text = "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        else:
            text = "" if content is None else str(content)
        return text.strip() if strip else text

    @staticmethod
    def _build_prompt(template_body: str, context: dict[str, Any]) -> str:
        parts = [f"模板内容：{template_body}"]
        key_labels = {
            "keyword": "搜索关键词",
            "username": "目标用户",
            "video_title": "视频标题",
        }
        for key, value in context.items():
            if isinstance(value, str) and value:
                parts.append(f"{key_labels.get(key, key)}：{value}")

        parts.append("请根据以上信息生成一条自然的评论/私信内容。只输出内容本身。")
        return "\n".join(parts)


ai_generator = AiGeneratorService()
