"""选择器管理业务域包。

集中声明选择器管理业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "selector_management"
PUBLIC_ROUTE_PREFIX = "/api/selectors"
