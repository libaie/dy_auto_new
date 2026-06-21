"""AI 视频系列业务域包。

集中声明AI 视频系列业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "ai_video_series"
PUBLIC_ROUTE_PREFIX = "/api/series"

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIX"]
