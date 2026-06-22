"""视频生产业务域模块。

视频生产业务域，负责生产计划、作业队列、provider 执行、审核门禁和资产状态流转。本文件负责 video_production_run_types 相关业务规则、状态转换和外部系统边界。
"""

from collections.abc import Iterable


REAL_SHORT_E2E = "real_short_e2e"
MOCK_SERIES_SCALE = "mock_series_scale"
LEGACY_EPISODE_RUN = "legacy_episode_run"

ALLOWED_RUN_TYPES = {REAL_SHORT_E2E, MOCK_SERIES_SCALE, LEGACY_EPISODE_RUN}
REAL_PROVIDER_RUN_TYPES = {REAL_SHORT_E2E}
MOCK_RUN_TYPES = {MOCK_SERIES_SCALE}


def validate_run_type(run_type: str | None) -> str:
    """业务函数：处理 validate_run_type 对应的业务流程、校验或数据转换。

    入参：run_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not run_type:
        return LEGACY_EPISODE_RUN
    if run_type not in ALLOWED_RUN_TYPES:
        raise ValueError(f"Unsupported video production run type: {run_type}")
    return run_type


def get_run_type(run) -> str:
    """业务函数：处理 get_run_type 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if not hasattr(run, "run_type"):
        raise ValueError("Video production run object is missing run_type")
    return validate_run_type(run.run_type)


def set_run_type(run, run_type: str) -> None:
    """业务函数：处理 set_run_type 对应的业务流程、校验或数据转换。

    入参：run、run_type 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    run.run_type = validate_run_type(run_type)


def assert_run_type(run, allowed: Iterable[str]) -> None:
    """业务函数：处理 assert_run_type 对应的业务流程、校验或数据转换。

    入参：run、allowed 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    current = get_run_type(run)
    allowed_types = list(allowed)
    if current not in allowed_types:
        raise ValueError(
            f"Video production run type {current} is not allowed; allowed: {allowed_types}"
        )


def is_real_provider_run(run) -> bool:
    """业务函数：处理 is_real_provider_run 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return get_run_type(run) in REAL_PROVIDER_RUN_TYPES


def is_mock_scale_run(run) -> bool:
    """业务函数：处理 is_mock_scale_run 对应的业务流程、校验或数据转换。

    入参：run 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    return get_run_type(run) in MOCK_RUN_TYPES
