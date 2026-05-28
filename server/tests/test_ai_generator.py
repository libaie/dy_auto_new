"""Tests for AI generator service with mocked HTTP calls."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.ai_generator import AiGeneratorService

pytestmark = pytest.mark.anyio


def _openai_cfg():
    return {
        "api_key": "test-key",
        "api_url": "https://api.example.test/v1/chat/completions",
        "model": "test-model",
        "thinking_enabled": False,
    }


def _anthropic_cfg():
    return {
        "api_key": "test-key",
        "api_url": "https://api.example.test/v1/messages",
        "model": "claude-test",
        "thinking_enabled": False,
    }


def _mock_response(json_data, status_code=200):
    """Create a mock httpx.Response that bypasses real raise_for_status."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _anthropic_response(text):
    return _mock_response({"content": [{"text": text}]})


def _openai_response(text):
    return _mock_response({"choices": [{"message": {"content": text}}]})


class _AsyncStreamResponse:
    def __init__(self, lines):
        self._lines = lines
        self.raised = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        self.raised = True

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _StreamClient:
    is_closed = False

    def __init__(self, lines):
        self.lines = lines
        self.calls = []

    def stream(self, method, url, headers=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        return _AsyncStreamResponse(self.lines)


class _FailingStreamResponse(_AsyncStreamResponse):
    def raise_for_status(self):
        raise httpx.ConnectError("connection refused")


class _FailingStreamClient(_StreamClient):
    def stream(self, method, url, headers=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        return _FailingStreamResponse(self.lines)


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

        with patch("app.config.get_ai_config_with_key", return_value={}), \
             pytest.raises(RuntimeError, match="AI API not configured"):
            await gen.generate(db, "body", {})

    async def test_happy_path(self, db):
        gen = AiGeneratorService()

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="good content") as mock_call:
            result = await gen.generate(db, "body", {"keyword": "test"})

        assert result == "good content"
        mock_call.assert_awaited_once()
        assert mock_call.await_args.args[0] == _openai_cfg()

    async def test_sensitive_retry_then_success(self, db):
        gen = AiGeneratorService()

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="normal content"), \
             patch("app.services.ai_generator.content_service") as mock_cs:
            mock_cs.contains_sensitive.side_effect = [True, False]
            result = await gen.generate(db, "body", {})

        assert result == "normal content"
        assert mock_cs.contains_sensitive.call_count == 2

    async def test_all_retries_sensitive_raises(self, db):
        gen = AiGeneratorService()

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="blocked content"), \
             patch("app.services.ai_generator.content_service") as mock_cs:
            mock_cs.contains_sensitive.return_value = True
            with pytest.raises(ValueError, match="All generated content contained sensitive words"):
                await gen.generate(db, "body", {})

    async def test_api_error_retry_then_success(self, db):
        gen = AiGeneratorService()

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                httpx.ConnectError("connection refused"),
                "good content",
            ]
            result = await gen.generate(db, "body", {})

        assert result == "good content"

    async def test_all_retries_api_fail_raises(self, db):
        gen = AiGeneratorService()

        with patch("app.config.get_ai_config_with_key", return_value=_openai_cfg()), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 2), \
             patch.object(gen, "_call_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = httpx.ConnectError("connection refused")
            with pytest.raises(RuntimeError, match="AI API failed after 2 attempts"):
                await gen.generate(db, "body", {})


class TestCallAnthropic:
    async def test_parses_response(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _anthropic_response("  generated content  ")
        gen._client = mock_client

        result = await gen._call_anthropic(_anthropic_cfg(), "test prompt")

        assert result == "generated content"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://api.example.test/v1/messages"
        assert call_args.kwargs["headers"]["x-api-key"] == "test-key"

    async def test_http_error_propagates(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _mock_response({}, status_code=500)
        gen._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await gen._call_anthropic(_anthropic_cfg(), "test prompt")


class TestCallOpenai:
    async def test_parses_response(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _openai_response("  generated content  ")
        gen._client = mock_client

        result = await gen._call_openai(_openai_cfg(), "test prompt")

        assert result == "generated content"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://api.example.test/v1/chat/completions"
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"

    async def test_http_error_propagates(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _mock_response({}, status_code=500)
        gen._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await gen._call_openai(_openai_cfg(), "test prompt")


class TestCallApiDispatch:
    async def test_dispatches_to_anthropic(self):
        gen = AiGeneratorService()

        with patch.object(gen, "_call_anthropic", new_callable=AsyncMock, return_value="ok") as mock:
            result = await gen._call_api(_anthropic_cfg(), "prompt")

        assert result == "ok"
        mock.assert_awaited_once_with(_anthropic_cfg(), "prompt")

    async def test_dispatches_to_openai(self):
        gen = AiGeneratorService()

        with patch.object(gen, "_call_openai", new_callable=AsyncMock, return_value="ok") as mock:
            result = await gen._call_api(_openai_cfg(), "prompt")

        assert result == "ok"
        mock.assert_awaited_once_with(_openai_cfg(), "prompt")


class TestGenerateCustomStreamWithConfig:
    async def test_streams_openai_compatible_chunks_without_db(self):
        gen = AiGeneratorService()
        client = _StreamClient([
            'data: {"choices":[{"delta":{"content":"{\\"a\\""}}]}',
            'data: {"choices":[{"delta":{"content":":1}"}}]}',
            "data: [DONE]",
        ])
        gen._client = client

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
        assert client.calls[0]["url"] == "https://api.example.test/v1/chat/completions"
        assert client.calls[0]["headers"]["Authorization"] == "Bearer test-key"
        assert client.calls[0]["json"]["max_tokens"] == 123
        assert client.calls[0]["json"]["temperature"] == 0.2
        assert client.calls[0]["json"]["messages"] == [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]

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

    async def test_stream_with_config_ignores_malformed_json_lines(self):
        gen = AiGeneratorService()
        client = _StreamClient([
            'data: {"choices":[{"delta":{"content":"before"}}]}',
            "data: {not valid json",
            'data: {"choices":[{"delta":{"content":"after"}}]}',
            "data: [DONE]",
        ])
        gen._client = client

        chunks = []
        async for chunk in gen.generate_custom_stream_with_config(
            _openai_cfg(),
            "system",
            "user",
        ):
            chunks.append(chunk)

        assert chunks == ["before", "after"]

    async def test_stream_with_config_raises_when_zero_retries_and_http_fails(self):
        gen = AiGeneratorService()
        client = _FailingStreamClient([])
        gen._client = client

        with patch("app.services.ai_generator.AI_MAX_RETRIES", 0), \
             pytest.raises(RuntimeError, match="generate_custom_stream_with_config failed after 1 attempts"):
            async for _chunk in gen.generate_custom_stream_with_config(
                _openai_cfg(),
                "system",
                "user",
            ):
                pass

        assert len(client.calls) == 1

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
