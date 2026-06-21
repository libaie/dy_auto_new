"""系统配置业务域模块。

系统配置业务域，负责安全配置、系统设置和加密存取。本文件负责 crypto 相关业务规则、状态转换和外部系统边界。
"""

import os
import hashlib
import base64
from cryptography.fernet import Fernet


def _get_key() -> bytes:
    """业务函数：处理 _get_key 对应的业务流程、校验或数据转换。"""
    raw = os.getenv("ENCRYPTION_KEY", "dy-auto-default-key-change-me")
    if raw == "dy-auto-default-key-change-me":
        return base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    derived = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(derived)


_cipher: Fernet | None = None


def _get_cipher() -> Fernet:
    """业务函数：处理 _get_cipher 对应的业务流程、校验或数据转换。"""
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
    """业务函数：处理 is_sensitive_key 对应的业务流程、校验或数据转换。"""
    return key in SENSITIVE_KEYS


def encrypt(value: str) -> str:
    """业务函数：处理 encrypt 对应的业务流程、校验或数据转换。"""
    return _get_cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """业务函数：处理 decrypt 对应的业务流程、校验或数据转换。"""
    return _get_cipher().decrypt(value.encode()).decode()
