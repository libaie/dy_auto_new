from typing import Any, Optional

from app.config import load_selectors_config


class SelectorService:
    """选择器配置服务 — 从 YAML 加载，支持按 action_name 查询"""

    def __init__(self):
        self._version: int = 0
        self._selectors: dict[str, dict] = {}
        self._load()

    def _load(self):
        version, selectors_list = load_selectors_config()
        self._version = version
        self._selectors = {s["action_name"]: s for s in selectors_list}

    def get_all_selectors(self) -> tuple[int, list[dict[str, Any]]]:
        """返回 (version, selectors_list)"""
        return self._version, list(self._selectors.values())

    def get_selector(self, action_name: str) -> Optional[dict[str, Any]]:
        """按 action_name 获取单个选择器配置"""
        return self._selectors.get(action_name)

    def get_version(self) -> int:
        return self._version
