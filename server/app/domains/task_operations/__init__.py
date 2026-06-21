"""任务运营业务域包。

集中声明任务运营业务域的公开边界，避免调用方感知内部文件拆分。
"""

DOMAIN_NAME = "task_operations"
PUBLIC_ROUTE_PREFIX = "/api/tasks"

__all__ = ["DOMAIN_NAME", "PUBLIC_ROUTE_PREFIX"]
