"""Seedance 集成业务域包。

集中声明Seedance 集成业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "seedance_integration"
PUBLIC_ROUTE_PREFIX = "/api/seedance"
PUBLIC_PROXY_PREFIX = "/api/seedance-proxy"
