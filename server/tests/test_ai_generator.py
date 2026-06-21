"""Tests for LangChain-backed AI generator service."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.domains.model_configuration.ai_generator import AiGeneratorService

pytestmark = pytest.mark.anyio


def _openai_cfg(**overrides):
    cfg = {
        "api_key": "test-key",
        "api_url": "https://api.example.test/v1/chat/completions",
        "model": "test-model",
        "thinking_enabled": False,
        "thinking_budget": 0,
    }
    cfg.update(overrides)
    return cfg


def _anthropic_cfg(**overrides):
    cfg = _openai_cfg(api_url="https://api.example.test/v1/messages", model="claude-test")
    cfg.update(overrides)
    return cfg


class TestBuildPrompt:
    def test_with_all_context(self):
        prompt = AiGeneratorService._build_prompt(
            "template {keyword}",
            {"keyword": "food", "username": "alice", "video_title": "hotpot"},
        )

        assert "template {keyword}" in prompt
        assert "food" in prompt
        assert "alice" in prompt
        assert "hotpot" in prompt

    def test_with_empty_context(self):
        prompt = AiGeneratorService._build_prompt("fixed body", {})

        assert "fixed body" in prompt
        assert "username" not in prompt

    def test_with_partial_context(self):
        prompt = AiGeneratorService._build_prompt("body", {"keyword": "test"})

        assert "test" in prompt
        assert "username" not in prompt


class TestGenerate:
    async def test_no_api_key_raises(self, db):
        gen = AiGeneratorService()

        with patch("app.config.get_ai_config_with_key", return_value=None), \
             pytest.raises(RuntimeError, match="AI API not configured"):
            await gen.generate(db, "body", {})

    async def test_happy_path(self, db):
        gen = AiGeneratorService()
        cfg = _openai_cfg()

        with patch("app.config.get_ai_config_with_key", return_value=cfg), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="good content") as mock_call:
            result = await gen.generate(db, "body", {"keyword": "test"})

        assert result == "good content"
        mock_call.assert_awaited_once()
        assert mock_call.await_args.args[0] == cfg

    async def test_sensitive_retry_then_success(self, db):
        gen = AiGeneratorService()
        cfg = _openai_cfg()

        with patch("app.config.get_ai_config_with_key", return_value=cfg), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="normal content"), \
             patch("app.domains.model_configuration.ai_generator.content_service") as mock_cs:
            mock_cs.contains_sensitive.side_effect = [True, False]
            result = await gen.generate(db, "body", {})

        assert result == "normal content"
        assert mock_cs.contains_sensitive.call_count == 2

    async def test_all_retries_sensitive_raises(self, db):
        gen = AiGeneratorService()
        cfg = _openai_cfg()

        with patch("app.config.get_ai_config_with_key", return_value=cfg), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="blocked content"), \
             patch("app.domains.model_configuration.ai_generator.content_service") as mock_cs:
            mock_cs.contains_sensitive.return_value = True
            with pytest.raises(ValueError, match="All generated content contained sensitive words"):
                await gen.generate(db, "body", {})

    async def test_api_error_retry_then_success(self, db):
        gen = AiGeneratorService()
        cfg = _openai_cfg()

        with patch("app.config.get_ai_config_with_key", return_value=cfg), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                httpx.ConnectError("connection refused"),
                "good content",
            ]
            result = await gen.generate(db, "body", {})

        assert result == "good content"

    async def test_all_retries_api_fail_raises(self, db):
        gen = AiGeneratorService()
        cfg = _openai_cfg()

        with patch("app.config.get_ai_config_with_key", return_value=cfg), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 2), \
             patch.object(gen, "_call_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = httpx.ConnectError("connection refused")
            with pytest.raises(RuntimeError, match="AI API failed after 2 attempts"):
                await gen.generate(db, "body", {})


class _FakeLangChainStreamModel:
    def __init__(self, chunks, fail_after_chunks=False):
        self.chunks = chunks
        self.fail_after_chunks = fail_after_chunks
        self.calls = []

    async def astream(self, messages):
        self.calls.append(messages)
        for chunk in self.chunks:
            yield MagicMock(content=chunk)
        if self.fail_after_chunks:
            raise RuntimeError("stream disconnected")


class _FailingLangChainStreamModel:
    def __init__(self):
        self.calls = 0

    async def astream(self, messages):
        self.calls += 1
        raise RuntimeError("connection refused")
        yield  # pragma: no cover


class TestCallAnthropic:
    async def test_anthropic_is_not_supported_without_langchain_provider(self):
        gen = AiGeneratorService()

        with pytest.raises(RuntimeError, match="OpenAI-compatible"):
            await gen._call_anthropic(_anthropic_cfg(), "test prompt")


class TestCallOpenai:
    async def test_invokes_langchain_model(self):
        gen = AiGeneratorService()
        fake_model = AsyncMock()
        fake_model.ainvoke.return_value = MagicMock(content="  generated content  ")

        with patch.object(gen, "_create_chat_model", return_value=fake_model) as create_model:
            result = await gen._call_openai(_openai_cfg(), "test prompt")

        assert result == "generated content"
        create_model.assert_called_once()
        assert fake_model.ainvoke.await_args.args[0] == [
            ("system", "你是一个抖音评论/私信内容生成助手。根据给定的模板和上下文，生成自然、友好的中文内容。\n规则：\n1. 保持内容自然，像真人写的\n2. 不要包含广告、链接、联系方式\n3. 不要包含敏感、违规、政治相关内容\n4. 内容长度控制在 20-100 字\n5. 直接输出生成的内容，不要加引号或解释"),
            ("human", "test prompt"),
        ]

    async def test_langchain_error_propagates(self):
        gen = AiGeneratorService()
        fake_model = AsyncMock()
        fake_model.ainvoke.side_effect = RuntimeError("boom")

        with patch.object(gen, "_create_chat_model", return_value=fake_model), \
             pytest.raises(RuntimeError, match="boom"):
            await gen._call_openai(_openai_cfg(), "test prompt")


class TestCallApiDispatch:
    async def test_rejects_anthropic(self):
        gen = AiGeneratorService()

        with pytest.raises(RuntimeError, match="OpenAI-compatible"):
            await gen._call_api(_anthropic_cfg(), "prompt")

    async def test_dispatches_to_openai(self):
        gen = AiGeneratorService()
        cfg = _openai_cfg()

        with patch.object(gen, "_call_openai", new_callable=AsyncMock, return_value="ok") as mock:
            result = await gen._call_api(cfg, "prompt")

        assert result == "ok"
        mock.assert_awaited_once_with(cfg, "prompt")


class TestGenerateCustom:
    async def test_uses_langchain_chat_model_for_openai_compatible_calls(self, db):
        gen = AiGeneratorService()
        fake_model = AsyncMock()
        fake_model.ainvoke.return_value = MagicMock(content="  generated content  ")

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch.object(gen, "_create_chat_model", return_value=fake_model) as create_model, \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 1):
            result = await gen.generate_custom(db, "system", "user", request_timeout_seconds=180)

        assert result == "generated content"
        create_model.assert_called_once()
        assert create_model.call_args.kwargs["request_timeout_seconds"] == 180
        assert fake_model.ainvoke.await_args.args[0] == [
            ("system", "system"),
            ("human", "user"),
        ]

    def test_builds_langchain_kwargs_from_legacy_openai_config(self):
        kwargs = AiGeneratorService._langchain_kwargs(
            _openai_cfg(),
            max_tokens=123,
            temperature=0.2,
            request_timeout_seconds=180,
        )

        assert kwargs["base_url"] == "https://api.example.test/v1"
        assert kwargs["model"] == "test-model"
        assert kwargs["max_tokens"] == 123
        assert kwargs["temperature"] == 0.2
        assert kwargs["timeout"] == 180.0

class TestGenerateCustomStreamWithConfig:
    async def test_streams_openai_compatible_chunks_without_db(self):
        gen = AiGeneratorService()
        model = _FakeLangChainStreamModel(['{"a"', ":1}"])

        with patch.object(gen, "_create_chat_model", return_value=model) as create_model:
            chunks = []
            async for chunk in gen.generate_custom_stream_with_config(
                _openai_cfg(),
                "system",
                "user",
                max_tokens=123,
                temperature=0.2,
            ):
                chunks.append(chunk)

        assert chunks == ['{"a"', ":1}"]
        assert model.calls[0] == [("system", "system"), ("human", "user")]
        assert create_model.call_args.kwargs["max_tokens"] == 123
        assert create_model.call_args.kwargs["temperature"] == 0.2

    async def test_stream_with_config_rejects_missing_api_key(self):
        gen = AiGeneratorService()

        with pytest.raises(RuntimeError, match="AI API not configured"):
            async for _chunk in gen.generate_custom_stream_with_config(
                {"api_key": "", "api_url": "https://api.example.test/v1/chat/completions"},
                "system",
                "user",
            ):
                pass

    async def test_stream_with_config_rejects_anthropic_api(self):
        gen = AiGeneratorService()

        with pytest.raises(RuntimeError, match="OpenAI-compatible"):
            async for _chunk in gen.generate_custom_stream_with_config(
                _anthropic_cfg(),
                "system",
                "user",
            ):
                pass

    async def test_stream_with_config_ignores_empty_chunks(self):
        gen = AiGeneratorService()
        model = _FakeLangChainStreamModel(["before", "", "after"])

        with patch.object(gen, "_create_chat_model", return_value=model):
            chunks = []
            async for chunk in gen.generate_custom_stream_with_config(
                _openai_cfg(),
                "system",
                "user",
            ):
                chunks.append(chunk)

        assert chunks == ["before", "after"]

    async def test_stream_with_config_raises_when_zero_retries_and_model_fails(self):
        gen = AiGeneratorService()
        model = _FailingLangChainStreamModel()

        with patch.object(gen, "_create_chat_model", return_value=model), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 0), \
             pytest.raises(RuntimeError, match="generate_custom_stream_with_config failed after 1 attempts"):
            async for _chunk in gen.generate_custom_stream_with_config(
                _openai_cfg(),
                "system",
                "user",
            ):
                pass

        assert model.calls == 1

    async def test_stream_with_config_does_not_retry_after_emitting_content(self):
        gen = AiGeneratorService()
        model = _FakeLangChainStreamModel(["partial"], fail_after_chunks=True)

        chunks = []
        with patch.object(gen, "_create_chat_model", return_value=model), \
             patch("app.domains.model_configuration.ai_generator.AI_MAX_RETRIES", 2), \
             pytest.raises(RuntimeError, match="streaming started"):
            async for chunk in gen.generate_custom_stream_with_config(
                _openai_cfg(),
                "system",
                "user",
            ):
                chunks.append(chunk)

        assert chunks == ["partial"]
        assert len(model.calls) == 1

    async def test_existing_db_stream_resolves_config_then_delegates(self, db):
        gen = AiGeneratorService()

        async def fake_stream(ai_cfg, system_prompt, user_prompt, max_tokens=4096, temperature=0.7):
            assert ai_cfg["api_key"] == "test-key"
            assert system_prompt == "system"
            assert user_prompt == "user"
            yield "ok"

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch.object(gen, "generate_custom_stream_with_config", side_effect=fake_stream):
            chunks = []
            async for chunk in gen.generate_custom_stream(db, "system", "user"):
                chunks.append(chunk)

        assert chunks == ["ok"]
