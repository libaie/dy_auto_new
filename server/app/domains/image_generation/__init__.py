"""图片生成业务域包。

集中声明图片生成业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "image_generation"
PUBLIC_ROUTE_PREFIXES = ("/api/image-creation", "/api/image-production")
