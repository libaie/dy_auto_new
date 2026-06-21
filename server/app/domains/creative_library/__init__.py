"""创意库业务域包。

集中声明创意库业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "creative_library"
PUBLIC_ROUTE_PREFIXES = (
    "/api/characters",
    "/api/scenes",
    "/api/reference-categories",
    "/api/reference-data",
)
