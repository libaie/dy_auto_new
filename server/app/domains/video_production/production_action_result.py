"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 production_action_result 相关业务规则、状态转换和外部系统边界。
"""

from dataclasses import dataclass, field

from app.domains.video_production.production_errors import ProductionErrorCode


def _serialize_code(code: ProductionErrorCode | str | None) -> str | None:
    """业务函数：处理 _serialize_code 对应的业务流程、校验或数据转换。

    入参：code 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if code is None:
        return None
    if isinstance(code, ProductionErrorCode):
        return code.value
    return str(code)


@dataclass
class ProductionActionResult:
    """业务类：承载 ProductionActionResult 相关的数据结构、状态或业务协作。

    类参数：affected_ids、code、data、message、repair_action、repair_route、retryable、status 承载该类的业务配置、状态或数据字段。
    """
    status: str
    message: str = ""
    code: ProductionErrorCode | str | None = None
    repair_action: str | None = None
    repair_route: str | None = None
    retryable: bool = False
    affected_ids: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    @classmethod
    def success(cls, message: str = "", data: dict | None = None) -> "ProductionActionResult":
        """业务函数：处理 success 对应的业务流程、校验或数据转换。

        入参：message、data 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        return cls(status="success", code="OK", message=message, data=data or {})

    @classmethod
    def blocked(
        cls,
        code: ProductionErrorCode | str,
        message: str,
        repair_action: str,
        repair_route: str | None = None,
        affected_ids: list[str] | None = None,
        retryable: bool = False,
        data: dict | None = None,
    ) -> "ProductionActionResult":
        """业务函数：处理 blocked 对应的业务流程、校验或数据转换。

        入参：code、message、repair_action、repair_route、affected_ids、retryable、data 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        return cls(
            status="blocked",
            code=code,
            message=message,
            repair_action=repair_action,
            repair_route=repair_route,
            retryable=retryable,
            affected_ids=affected_ids or [],
            data=data or {},
        )

    def to_http_detail(self) -> dict:
        """业务函数：处理 to_http_detail 对应的业务流程、校验或数据转换。

        入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
        出参：返回该业务流程的处理结果；无显式返回值时返回 None。
        """
        code = _serialize_code(self.code)
        return {
            "ok": self.status == "success",
            "status": self.status,
            "code": code,
            "error_code": code,
            "message": self.message,
            "repair_action": self.repair_action,
            "repair_route": self.repair_route,
            "retryable": self.retryable,
            "affected_ids": self.affected_ids,
            "data": self.data,
        }
