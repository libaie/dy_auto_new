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
    if not run_type:
        return LEGACY_EPISODE_RUN
    if run_type not in ALLOWED_RUN_TYPES:
        raise ValueError(f"Unsupported video production run type: {run_type}")
    return run_type


def get_run_type(run) -> str:
    if not hasattr(run, "run_type"):
        raise ValueError("Video production run object is missing run_type")
    return validate_run_type(run.run_type)


def set_run_type(run, run_type: str) -> None:
    run.run_type = validate_run_type(run_type)


def assert_run_type(run, allowed: Iterable[str]) -> None:
    current = get_run_type(run)
    allowed_types = list(allowed)
    if current not in allowed_types:
        raise ValueError(
            f"Video production run type {current} is not allowed; allowed: {allowed_types}"
        )


def is_real_provider_run(run) -> bool:
    return get_run_type(run) in REAL_PROVIDER_RUN_TYPES


def is_mock_scale_run(run) -> bool:
    return get_run_type(run) in MOCK_RUN_TYPES
