"""Bind observed templates to a selector revision and target application version."""
import base64
import binascii
import copy
import hashlib
import re

from sqlalchemy.orm import Session

from app.db_models import UISelector
from app.services.selector_service import _bump_revision
from app.services.template_service import template_service


class CalibrationError(ValueError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code


def publish_calibration(db: Session, items: list[dict], resolution: str) -> int:
    """Validate the whole batch before writing files or publishing configuration.

    Legacy clients without source IDs remain supported only when their source
    profile is unambiguous. A failed DB commit may leave an unreferenced immutable
    asset; it cannot replace an asset used by another selector.
    """
    prepared = []
    seen = set()
    for item in items:
        action = item["action_name"]
        query = db.query(UISelector).filter(UISelector.action_name == action, UISelector.enabled.is_(True))
        if item.get("source_selector_id"):
            query = query.filter(UISelector.id == item["source_selector_id"])
            if item.get("source_selector_version") is None:
                raise CalibrationError(400, "标定必须包含来源选择器版本")
        else:
            query = query.filter(UISelector.resolution_profile == item.get("source_resolution_profile", "default"))
            if item.get("source_platform_version"):
                query = query.filter(UISelector.platform_version == item["source_platform_version"])
        sources = query.with_for_update().all()
        if not sources:
            raise CalibrationError(409, f"来源选择器不存在或已禁用: {action}")
        if len(sources) != 1:
            raise CalibrationError(409, f"标定来源版本不唯一，请更新设备配置: {action}")
        source = sources[0]
        if item.get("source_selector_version") is not None and item["source_selector_version"] != source.version:
            raise CalibrationError(409, f"来源选择器已更新，请重新定位并标定: {action}")
        if source.purpose in ("page_detect", "extract"):
            raise CalibrationError(400, "自动标定仅用于定位动作")
        platform = item.get("platform_version") or source.platform_version or "default"
        key = (action, platform, resolution)
        if key in seen:
            raise CalibrationError(400, f"同一标定批次包含重复动作: {action}")
        seen.add(key)
        try:
            # Android Base64.DEFAULT inserts newlines; allow whitespace only.
            content = base64.b64decode("".join(item["data"].split()), validate=True)
        except (ValueError, binascii.Error):
            raise CalibrationError(400, f"模板 Base64 无效: {action}") from None
        if not content or len(content) > 5 * 1024 * 1024:
            raise CalibrationError(400, "模板大小必须介于 1 字节与 5MB 之间")
        source_resolution = item.get("source_resolution") or resolution
        safe_action = re.sub(r"[^A-Za-z0-9_.-]", "_", action)[:100]
        digest = hashlib.sha256(content).hexdigest()[:20]
        filename = f"{safe_action}@{source_resolution}_{digest}.png"
        existing = db.query(UISelector).filter_by(action_name=action, platform_version=platform, resolution_profile=resolution).with_for_update().all()
        if len(existing) > 1:
            raise CalibrationError(409, f"目标选择器存在重复配置，请先整理: {action}")
        prepared.append((item, source, existing[0] if existing else None, platform, source_resolution, filename, content))

    for item, source, target, platform, source_resolution, filename, content in prepared:
        template_service.save_template(filename, content, resolution=resolution)
        strategies = copy.deepcopy((target or source).strategies)
        image_strategies = [strategy for strategy in strategies if strategy.get("type") == "image"]
        if not image_strategies:
            priorities = [s.get("priority", 0) for s in strategies if isinstance(s.get("priority", 0), (int, float))]
            image_strategy = {"type": "image", "priority": max(priorities, default=0) + 1, "threshold": 0.85}
            strategies.append(image_strategy)
            image_strategies.append(image_strategy)
        for strategy in image_strategies:
            strategy["template"] = filename
            strategy["source_resolution"] = source_resolution
            # A calibrated asset has a new native scale; old literal multipliers
            # from its predecessor must not be applied to it.
            strategy.pop("scales", None)
            strategy.pop("source_density", None)
            if item.get("source_density") is not None:
                strategy["source_density"] = item["source_density"]
            strategy["calibration"] = {"source_selector_id": source.id, "source_selector_version": source.version, "platform_version": platform}
        if target is not None:
            target.strategies = strategies
            target.version += 1
        else:
            target = UISelector(
                action_name=source.action_name, description=source.description,
                platform_version=platform, resolution_profile=resolution,
                strategies=strategies, version=1, category=source.category,
                purpose=source.purpose, strategy_logic=source.strategy_logic,
                extract_field=source.extract_field, clean_mode=source.clean_mode,
                clean_pattern=source.clean_pattern, clean_prompt=source.clean_prompt,
            )
            db.add(target)
    if prepared:
        _bump_revision(db)
    db.commit()
    return len(prepared)
