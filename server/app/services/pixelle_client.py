"""Pixelle-Video HTTP client — unified request with retry, lazy singleton."""
import asyncio
import json
import logging
import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8500"
TIMEOUT = httpx.Timeout(600, connect=10)
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds, exponential: 2, 4, 8

_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None
_base_url: str = ""


def _normalize_base_url(value: str | None) -> str:
    clean = (value or DEFAULT_BASE_URL).strip().rstrip("/")
    if clean.endswith("/api"):
        clean = clean[:-4]
    return clean or DEFAULT_BASE_URL


def _get_base_url(db: Session | None = None) -> str:
    global _base_url
    if _base_url:
        return _normalize_base_url(_base_url)
    if db is not None:
        try:
            from app.db_models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "pixelle_video_url").first()
            if row and row.value:
                _base_url = _normalize_base_url(row.value)
                return _base_url
        except Exception:
            pass
    _base_url = _normalize_base_url(DEFAULT_BASE_URL)
    return _base_url


def _get_api_key(db: Session | None = None) -> str:
    if db is not None:
        try:
            from app.db_models import SystemSetting
            row = db.query(SystemSetting).filter(SystemSetting.key == "pixelle_api_key").first()
            if row and row.value:
                return str(row.value)
        except Exception:
            pass
    from app.config import PIXELLE_API_KEY
    return PIXELLE_API_KEY


def _get_client() -> httpx.AsyncClient:
    global _client, _client_loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _client is None or getattr(_client, "is_closed", False) or _client_loop is not loop:
        _client = httpx.AsyncClient(timeout=TIMEOUT, trust_env=False)
        _client_loop = loop
    return _client


async def close_client():
    """Close the module-level httpx client. Call during app shutdown."""
    global _client, _client_loop
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        _client_loop = None


async def _pixelle_request(method: str, path: str, db: Session | None = None, **kwargs) -> dict:
    """统一的 Pixelle-Video HTTP 请求入口，带指数退避重试."""
    url = f"{_get_base_url(db)}{path}"
    client = _get_client()
    last_err = None

    headers = kwargs.pop("headers", {})
    api_key = _get_api_key(db)
    if api_key:
        headers["X-API-Key"] = api_key

    for attempt in range(MAX_RETRIES):
        try:
            r = await client.request(method, url, headers=headers, **kwargs)
            r.raise_for_status()
            try:
                return r.json()
            except json.JSONDecodeError:
                raw = r.text[:500]
                logger.error("Pixelle-Video returned non-JSON response: %s", raw)
                raise RuntimeError(f"Pixelle-Video returned invalid JSON (status={r.status_code}): {raw}")
        except RuntimeError:
            raise  # JSON decode error — don't retry, it's not transient
        except httpx.HTTPStatusError as e:
            last_err = e
            if e.response.status_code < 500:
                raise  # 4xx — don't retry client errors
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_err = e
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_BACKOFF * (2 ** attempt)
            logger.warning("Pixelle %s %s attempt %d/%d failed, retrying in %.0fs: %s",
                           method, path, attempt + 1, MAX_RETRIES, delay, last_err)
            await asyncio.sleep(delay)
    raise last_err
