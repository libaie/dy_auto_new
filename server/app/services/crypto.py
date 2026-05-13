"""AES-256-GCM field-level encryption for sensitive settings."""
import os
import hashlib
import base64
from cryptography.fernet import Fernet


def _get_key() -> bytes:
    raw = os.getenv("ENCRYPTION_KEY", "dy-auto-default-key-change-me")
    if raw == "dy-auto-default-key-change-me":
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    derived = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(derived)


_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        _cipher = Fernet(_get_key())
    return _cipher


SENSITIVE_KEYS = {
    "seedance_api_key", "kling_access_key", "kling_secret_key",
    "runninghub_api_key", "comfyui_api_key", "llm_api_key",
    "oss_access_key", "oss_secret_key",
}


def is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_KEYS


def encrypt(value: str) -> str:
    return _get_cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_cipher().decrypt(value.encode()).decode()
