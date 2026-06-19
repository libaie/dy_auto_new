"""Payload shaping helpers for account operations routes."""


def account_to_dict(acc) -> dict:
    return {
        "id": acc.id,
        "nickname": acc.nickname,
        "douyin_id": acc.douyin_id,
        "group": acc.group,
        "status": acc.status,
        "daily_limits": acc.daily_limits,
        "created_at": str(acc.created_at) if acc.created_at else None,
        "updated_at": str(acc.updated_at) if acc.updated_at else None,
    }


def group_to_dict(group, member_count: int = 0) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description or "",
        "member_count": member_count,
        "created_at": str(group.created_at) if group.created_at else None,
        "updated_at": str(group.updated_at) if group.updated_at else None,
    }


def member_to_dict(account) -> dict:
    return {
        "id": account.id,
        "nickname": account.nickname,
        "douyin_id": account.douyin_id,
        "status": account.status,
    }


def channel_to_response(channel, stats: dict, group_name: str = "") -> dict:
    return {
        "id": channel.id,
        "group_id": channel.group_id,
        "group_name": group_name,
        "task_type": channel.task_type,
        "status": channel.status,
        "account_mode": channel.account_mode,
        "account_id": channel.account_id or "",
        "params_template": channel.params_template or {},
        "cooldown_seconds": channel.cooldown_seconds,
        "delay_range": channel.delay_range or [3000, 8000],
        "total": stats["total"],
        "pending": stats["pending"],
        "assigned": stats["assigned"],
        "completed": stats["completed"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "created_at": str(channel.created_at) if channel.created_at else None,
        "completed_at": str(channel.completed_at) if channel.completed_at else None,
    }


def channel_item_to_response(item, account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": item.id,
        "keyword": item.keyword,
        "account_id": item.account_id,
        "account_nickname": account_nickname,
        "status": item.status,
        "assigned_device_id": item.assigned_device_id or "",
        "device_name": device_name,
        "task_id": item.task_id or "",
        "queue_position": item.queue_position,
        "created_at": str(item.created_at) if item.created_at else None,
        "completed_at": str(item.completed_at) if item.completed_at else None,
    }


def chain_template_to_dict(template) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description or "",
        "steps": template.steps or [],
        "created_at": str(template.created_at) if template.created_at else None,
        "updated_at": str(template.updated_at) if template.updated_at else None,
    }


def chain_instance_to_dict(instance, template_name: str = "", account_nickname: str = "", device_name: str = "") -> dict:
    return {
        "id": instance.id,
        "template_id": instance.template_id,
        "template_name": template_name,
        "account_id": instance.account_id,
        "account_nickname": account_nickname,
        "device_id": instance.device_id or "",
        "device_name": device_name,
        "current_step": instance.current_step,
        "total_steps": instance.total_steps,
        "status": instance.status,
        "created_at": str(instance.created_at) if instance.created_at else None,
        "started_at": str(instance.started_at) if instance.started_at else None,
        "completed_at": str(instance.completed_at) if instance.completed_at else None,
    }
