"""行业合规Profile加载器 — 从 JSON 文件加载，LRU 缓存"""
import json
import os
from functools import lru_cache

PROFILES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "industry_profiles"
)


@lru_cache(maxsize=8)
def load_profile(industry: str) -> dict:
    """加载行业合规Profile，文件不存在时回退到 general.json"""
    path = os.path.join(PROFILES_DIR, f"{industry}.json")
    if not os.path.exists(path):
        path = os.path.join(PROFILES_DIR, "general.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_industries() -> list[dict]:
    """返回可用行业列表供前端下拉使用"""
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
