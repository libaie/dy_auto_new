"""Tests for pixelle_client — mock httpx, cover all retry/error branches."""
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.pixelle_client import _pixelle_request, _get_base_url, DEFAULT_BASE_URL


class TestPixelleRequest:
    """_pixelle_request — retry, error, and success paths."""

    @pytest.mark.asyncio
    async def test_success_returns_parsed_json(self):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"ok": True, "result": "done"})
        resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("app.services.pixelle_client._get_client", return_value=mock_client):
            result = await _pixelle_request("POST", "/test", json={"x": 1})

        assert result == {"ok": True, "result": "done"}
        assert mock_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_5xx_then_success(self):
        fail_resp = MagicMock()
        fail_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock(status_code=500)))
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.raise_for_status = MagicMock()
        ok_resp.json = MagicMock(return_value={"ok": True})
        ok_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[fail_resp, fail_resp, ok_resp])

        with patch("app.services.pixelle_client._get_client", return_value=mock_client):
            result = await _pixelle_request("GET", "/test")

        assert result == {"ok": True}
        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self):
        resp = MagicMock()
        resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=MagicMock(status_code=400)))
        resp.status_code = 400

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("app.services.pixelle_client._get_client", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await _pixelle_request("POST", "/test", json={})

        assert mock_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_connect_error_retry(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            httpx.ConnectError("refused"),
            httpx.ConnectError("refused"),
            httpx.ConnectError("refused"),
        ])

        with patch("app.services.pixelle_client._get_client", return_value=mock_client):
            with pytest.raises(httpx.ConnectError):
                await _pixelle_request("GET", "/test")

        assert mock_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_json_decode_error_raises_runtime_error(self):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(side_effect=json.JSONDecodeError("msg", "doc", 0))
        resp.text = "not json"
        resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)

        with patch("app.services.pixelle_client._get_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                await _pixelle_request("POST", "/test")

        assert mock_client.request.call_count == 1  # no retry on JSON error

    @pytest.mark.asyncio
    async def test_retries_exhausted_timeout(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
        ])

        with patch("app.services.pixelle_client._get_client", return_value=mock_client):
            with pytest.raises(httpx.TimeoutException):
                await _pixelle_request("GET", "/test")

        assert mock_client.request.call_count == 3


class TestGetBaseUrl:
    """_get_base_url — SystemSetting fallback."""

    def test_returns_default_when_no_db(self):
        from app.services import pixelle_client
        pixelle_client._base_url = ""
        url = _get_base_url(db=None)
        assert url == DEFAULT_BASE_URL

    def test_returns_cached_url(self):
        from app.services import pixelle_client
        pixelle_client._base_url = "http://custom:9999/api"
        url = _get_base_url(db=None)
        assert url == "http://custom:9999/api"
        pixelle_client._base_url = ""  # reset
