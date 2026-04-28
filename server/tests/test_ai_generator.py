"""Tests for AI generator service -- mocked HTTP calls, retry logic, prompt building."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.ai_generator import AiGeneratorService

pytestmark = pytest.mark.anyio


# --- Helper: mock httpx response ---

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


# --- _build_prompt tests ---

class TestBuildPrompt:
    def test_with_all_context(self):
        prompt = AiGeneratorService._build_prompt(
            "关于{keyword}的视频", {"keyword": "美食", "username": "小明", "video_title": "火锅"}
        )
        assert "模板内容：关于{keyword}的视频" in prompt
        assert "搜索关键词：美食" in prompt
        assert "目标用户：小明" in prompt
        assert "视频标题：火锅" in prompt
        assert "只输出内容本身" in prompt

    def test_with_empty_context(self):
        prompt = AiGeneratorService._build_prompt("固定文本", {})
        assert "模板内容：固定文本" in prompt
        assert "搜索关键词" not in prompt
        assert "目标用户" not in prompt

    def test_with_partial_context(self):
        prompt = AiGeneratorService._build_prompt("body", {"keyword": "test"})
        assert "搜索关键词：test" in prompt
        assert "目标用户" not in prompt


# --- generate() tests ---

class TestGenerate:
    async def test_no_api_key_raises(self, db):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_API_KEY", ""):
            with pytest.raises(RuntimeError, match="AI_API_KEY not configured"):
                await gen.generate(db, "body", {})

    async def test_happy_path(self, db):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="好内容"):
            result = await gen.generate(db, "body", {"keyword": "test"})
            assert result == "好内容"

    async def test_sensitive_retry_then_success(self, db):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="正常内容"), \
             patch("app.services.ai_generator.content_service") as mock_cs:
            # First call: sensitive, second call: clean
            mock_cs.contains_sensitive.side_effect = [True, False]
            result = await gen.generate(db, "body", {})
            assert result == "正常内容"
            assert mock_cs.contains_sensitive.call_count == 2

    async def test_all_retries_sensitive_raises(self, db):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock, return_value="赌博内容"), \
             patch("app.services.ai_generator.content_service") as mock_cs:
            mock_cs.contains_sensitive.return_value = True
            with pytest.raises(ValueError, match="All generated content contained sensitive words"):
                await gen.generate(db, "body", {})

    async def test_api_error_retry_then_success(self, db):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 3), \
             patch.object(gen, "_call_api", new_callable=AsyncMock) as mock_call:
            # First call: HTTP error, second call: success
            mock_call.side_effect = [
                httpx.ConnectError("connection refused"),
                "好内容",
            ]
            result = await gen.generate(db, "body", {})
            assert result == "好内容"

    async def test_all_retries_api_fail_raises(self, db):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_API_KEY", "test-key"), \
             patch("app.services.ai_generator.AI_MAX_RETRIES", 2), \
             patch.object(gen, "_call_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = httpx.ConnectError("connection refused")
            with pytest.raises(RuntimeError, match="AI API failed after 2 attempts"):
                await gen.generate(db, "body", {})


# --- _call_anthropic tests ---

class TestCallAnthropic:
    async def test_parses_response(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _anthropic_response("  生成的内容  ")
        gen._client = mock_client

        result = await gen._call_anthropic("test prompt")
        assert result == "生成的内容"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/v1/messages" in call_args[0][0]

    async def test_http_error_propagates(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _mock_response({}, status_code=500)
        gen._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await gen._call_anthropic("test prompt")


# --- _call_openai tests ---

class TestCallOpenai:
    async def test_parses_response(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _openai_response("  生成的内容  ")
        gen._client = mock_client

        result = await gen._call_openai("test prompt")
        assert result == "生成的内容"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/v1/chat/completions" in call_args[0][0]

    async def test_http_error_propagates(self):
        gen = AiGeneratorService()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = _mock_response({}, status_code=500)
        gen._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await gen._call_openai("test prompt")


# --- _call_api dispatch tests ---

class TestCallApiDispatch:
    async def test_dispatches_to_anthropic(self):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_PROVIDER", "anthropic"), \
             patch.object(gen, "_call_anthropic", new_callable=AsyncMock, return_value="ok") as mock:
            result = await gen._call_api("prompt")
            assert result == "ok"
            mock.assert_called_once_with("prompt")

    async def test_dispatches_to_openai(self):
        gen = AiGeneratorService()
        with patch("app.services.ai_generator.AI_PROVIDER", "openai"), \
             patch.object(gen, "_call_openai", new_callable=AsyncMock, return_value="ok") as mock:
            result = await gen._call_api("prompt")
            assert result == "ok"
            mock.assert_called_once_with("prompt")
