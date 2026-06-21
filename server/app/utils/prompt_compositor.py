"""提示词组合工具。

负责把业务上下文、模板和变量组合为模型可消费的提示词。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ProductionScene, ProductionShot
from app.models.asset_anchor import ComposedShotPrompt
from app.domains.creative_library.anchor_service import AssetAnchorManager


DEFAULT_SEED_SCHEMA = {"seed": {"type": "number"}}


class AssetPromptCompositor:
    def __init__(self, db: Session):
        self.db = db
        self.anchor_manager = AssetAnchorManager(db)

    def compose_shot_prompt(
        self,
        shot_id: str,
        *,
        provider: str = "pixelle",
        provider_options_schema: dict[str, Any] | None = None,
        video_model_name: str | None = None,
        input_image_url: str | None = None,
    ) -> ComposedShotPrompt:
        if _requires_input_image_url(video_model_name) and not str(input_image_url or "").strip():
            raise ValueError("input_image_url is required for Wan 2.7 image-to-video generation")

        shot = self._shot(shot_id)
        production_scene = (
            self.db.query(ProductionScene)
            .filter(ProductionScene.id == shot.scene_plan_id)
            .first()
        )
        scene_anchor = self.anchor_manager.latest_scene_anchor(production_scene.scene_id if production_scene else None)
        character_anchors = self.anchor_manager.latest_character_anchors(_shot_character_ids(shot))
        payload = self.anchor_manager.adapt_provider_parameters(
            character_anchors=character_anchors,
            scene_anchor=scene_anchor,
            provider=provider,
            provider_options_schema=provider_options_schema if provider_options_schema is not None else DEFAULT_SEED_SCHEMA,
        )

        parts = []
        if scene_anchor and scene_anchor.environment_prompt:
            parts.append(scene_anchor.environment_prompt)
        parts.extend(anchor.base_prompt for anchor in character_anchors if anchor.base_prompt)
        action = _action_and_emotion_description(shot)
        if action:
            parts.append(action)

        prompt = "\n".join(part.strip() for part in parts if str(part or "").strip())
        if not prompt:
            prompt = shot.action or shot.shot_id
        return ComposedShotPrompt(
            shot_id=shot.id,
            prompt=prompt,
            seed=payload.seed,
            provider_options=payload.provider_options,
            reference_images=payload.reference_images,
            reference_urls=[item["url"] for item in payload.reference_images if item.get("url")],
            input_image_url=input_image_url,
        )

    def _shot(self, shot_id: str) -> ProductionShot:
        shot = self.db.query(ProductionShot).filter(ProductionShot.id == shot_id).first()
        if not shot:
            shot = self.db.query(ProductionShot).filter(ProductionShot.shot_id == shot_id).first()
        if not shot:
            raise ValueError(f"Production shot not found: {shot_id}")
        return shot


def _shot_character_ids(shot: ProductionShot) -> list[str]:
    value = shot.character_ids or []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _action_and_emotion_description(shot: ProductionShot) -> str:
    action = str(shot.action or "").strip()
    emotion = str(shot.emotion or "").strip()
    if action and emotion:
        return f"{action}\nEmotion: {emotion}"
    return action or (f"Emotion: {emotion}" if emotion else "")


def _requires_input_image_url(video_model_name: str | None) -> bool:
    name = str(video_model_name or "").lower().replace(" ", "")
    return "wan" in name and ("2.7" in name or "wan2.7" in name)
