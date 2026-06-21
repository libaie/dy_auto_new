"""剧本流水线业务域包。

集中声明剧本流水线业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "script_pipeline"
PUBLIC_ROUTE_PREFIX = "/api/pipeline"
