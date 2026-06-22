"""行业合规Profile加载器 — 从 JSON 文件加载，LRU 缓存"""
import json
import os
from functools import lru_cache

PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "industry_profiles"
)


@lru_cache(maxsize=8)
def load_profile(industry: str) -> dict:
    """业务函数：处理 load_profile 对应的业务流程、校验或数据转换。

    入参：industry 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    path = os.path.join(PROFILES_DIR, f"{industry}.json")
    if not os.path.exists(path):
        path = os.path.join(PROFILES_DIR, "general.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_industries() -> list[dict]:
    """业务函数：处理 list_industries 对应的业务流程、校验或数据转换。

    入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    result = []
    try:
        for fname in sorted(os.listdir(PROFILES_DIR)):
            if fname.endswith(".json"):
                with open(os.path.join(PROFILES_DIR, fname), "r", encoding="utf-8") as f:
                    profile = json.load(f)
                    result.append({"key": profile["industry"], "label": profile["label"]})
    except FileNotFoundError:
        pass
    return result
