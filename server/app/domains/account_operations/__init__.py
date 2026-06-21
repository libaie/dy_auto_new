"""账号运营业务域包。

集中声明账号运营业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "account_operations"
PUBLIC_ROUTE_PREFIXES = ("/api/accounts", "/api/account-groups", "/api/channels", "/api/chains")

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIXES"]
