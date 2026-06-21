"""设备运营业务域包。

集中声明设备运营业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "device_operations"
PUBLIC_ROUTE_PREFIXES = ("/api/device", "/api/devices")

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIXES"]
