"""内容采集业务域包。

集中声明内容采集业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "content_collection"
PUBLIC_ROUTE_PREFIXES = ("/api/content", "/api/data", "/api/dm-sequences")
