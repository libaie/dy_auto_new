"""任务运营业务域模块。

任务运营业务域，负责任务参数解析、执行用例、实时事件和路由接口。本文件负责 param_resolution 相关业务规则、状态转换和外部系统边界。
"""

import logging

from app.models import TaskType

from .adapters import content_service

logger = logging.getLogger(__name__)


async def maybe_resolve_content_template(params: dict, task_type: str, db=None) -> dict:
    """业务函数：处理 maybe_resolve_content_template 对应的业务流程、校验或数据转换。

    入参：params、task_type、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """If params has content_template_id, resolve it into params.content."""
    template_id = params.get("content_template_id")
    if not template_id:
        return params
    try:
        keyword = params.get("keyword") or (params.get("keywords", [None])[0]) or ""
        context = {"keyword": keyword, "task_type": task_type}
        generated = await content_service.generate_from_template(db, template_id, context)
        params["content"] = generated
        logger.info("Resolved content_template_id=%s for task_type=%s", template_id, task_type)
    except Exception as e:
        logger.warning("Failed to resolve content_template_id=%s: %s", template_id, e)
    return params


async def maybe_resolve_dm_sequence(params: dict, db=None) -> dict:
    """业务函数：处理 maybe_resolve_dm_sequence 对应的业务流程、校验或数据转换。

    入参：params、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Resolve dm_sequence_id into inline messages while preserving the id."""
    seq_id = params.get("dm_sequence_id")
    if not seq_id or not db:
        return params
    try:
        from app.db.models.content_collection import DMSequence

        seq = db.query(DMSequence).filter(DMSequence.id == seq_id).first()
        if seq and seq.messages:
            params["dm_messages"] = seq.messages
            first = seq.messages[0]
            if isinstance(first, dict):
                params["content"] = first.get("content", "")
            logger.info("Resolved dm_sequence_id=%s into %d inline messages (id preserved for variants)", seq_id, len(seq.messages))
        else:
            logger.warning("dm_sequence_id=%s not found in DB, removing from params", seq_id)
            params.pop("dm_sequence_id", None)
    except Exception as e:
        logger.warning("Failed to resolve dm_sequence_id=%s: %s", seq_id, e)
        params.pop("dm_sequence_id", None)
    return params


async def maybe_expand_keywords(params: dict, task_type: str, db=None) -> dict:
    """业务函数：处理 maybe_expand_keywords 对应的业务流程、校验或数据转换。

    入参：params、task_type、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """If nurture task has keywords, expand them into keyword_matrix via AI."""
    if task_type != "nurture" or "keywords" not in params:
        return params
    seeds = [k.strip() for k in params.get("keywords", []) if k and k.strip()]
    if not seeds:
        return params
    existing_matrix = [k.strip() for k in params.get("keyword_matrix", []) if k and k.strip()]
    if existing_matrix:
        params["keyword_matrix"] = list(dict.fromkeys(seeds + existing_matrix))
        return params
    try:
        all_expanded = []
        for seed in seeds[:3]:
            expand_count = int(params.get("expand_count", 8))
            expanded = await content_service.generate_keyword_matrix(seed, expand_count, db=db)
            all_expanded.extend(expanded)
        unique = list(dict.fromkeys(seeds + all_expanded))
        params["keyword_matrix"] = unique
        for kw in all_expanded:
            logger.info("AI expanded keyword: %s", kw)
    except Exception as e:
        logger.warning("Failed to expand keywords for nurture task: %s", e)
    return params


def maybe_resolve_nurture_subtask_templates(params: dict, task_type: str, db=None) -> dict:
    """业务函数：处理 maybe_resolve_nurture_subtask_templates 对应的业务流程、校验或数据转换。

    入参：params、task_type、db 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if task_type != "nurture" or not db:
        return params
    sub_tasks = params.get("sub_tasks")
    if not isinstance(sub_tasks, list):
        return params
    keyword = params.get("keyword") or ""
    if not keyword:
        keywords = params.get("keywords") or params.get("keyword_matrix") or []
        if keywords:
            keyword = keywords[0]
    for sub_task in sub_tasks:
        if not isinstance(sub_task, dict) or sub_task.get("type") != "comment":
            continue
        template_id = sub_task.get("content_template_id")
        if not template_id or sub_task.get("content"):
            continue
        try:
            tpl_body = content_service.get_template_body(db, template_id)
            if tpl_body:
                sub_task["content"] = content_service.substitute_variables(
                    tpl_body, {"keyword": keyword}
                )
        except Exception as e:
            logger.warning("Failed to resolve nurture sub_task template=%s: %s", template_id, e)
    return params


def resolve_task_type(type_val) -> TaskType:
    """业务函数：处理 resolve_task_type 对应的业务流程、校验或数据转换。

    入参：type_val 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    if isinstance(type_val, TaskType):
        return type_val
    return TaskType(type_val)


def validate_and_normalize_params(task_type: str, params: dict) -> dict:
    """业务函数：处理 validate_and_normalize_params 对应的业务流程、校验或数据转换。

    入参：task_type、params 为该业务流程需要的上下文、标识或载荷。
    出参：返回该业务流程的处理结果；无显式返回值时返回 None。
    """
    """Validate and normalize task params using models.TASK_PARAMS_VALIDATORS."""
    from app.models import TASK_PARAMS_VALIDATORS
    from pydantic import BaseModel as PydanticBase

    validator = TASK_PARAMS_VALIDATORS.get(task_type)
    if validator is None:
        return params

    if callable(validator) and not isinstance(validator, type):
        return validator(params)
    if isinstance(validator, type) and issubclass(validator, PydanticBase):
        validated = validator(**params)
        return validated.model_dump(exclude_none=True)
    return params
