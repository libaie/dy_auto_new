from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.creative_library import CharacterAnchor as CharacterAnchorRow
from app.db.models.creative_library import SceneAnchor as SceneAnchorRow
from app.db_models import Character, Scene
from app.models.asset_anchor import (
    AnchorProviderPayload,
    AnchorReferenceImage,
    AnchorReferenceMode,
    AnchorStatus,
    MAX_PROVIDER_SEED,
)
from app.domains.video_production.production_status import REFERENCE_CHARACTER_ANCHOR, REFERENCE_SCENE_REFERENCE
from app.domains.creative_library.reference_asset_service import (
    CHARACTER_REFERENCE_SLOTS,
    SCENE_EMPTY_PLATE_INSTRUCTION,
    SCENE_REFERENCE_SLOTS,
    generate_reference_url,
    reference_url_is_usable,
)


CHARACTER_SLOT_REF_MODES = {
    "avatar_front_url": AnchorReferenceMode.CONTROLNET_FACE.value,
    "avatar_side_url": AnchorReferenceMode.CONTROLNET_FACE.value,
    "avatar_threequarter_url": AnchorReferenceMode.CONTROLNET_FACE.value,
    "avatar_fullbody_url": AnchorReferenceMode.IMAGE_TO_IMAGE.value,
}
SCENE_SLOT_REF_MODES = {
    "reference_wideshot_url": AnchorReferenceMode.IMAGE_TO_IMAGE.value,
    "reference_midshot_url": AnchorReferenceMode.IMAGE_TO_IMAGE.value,
    "reference_aerial_url": AnchorReferenceMode.IMAGE_TO_IMAGE.value,
}


class AssetAnchorManager:
    def __init__(self, db: Session):
        self.db = db

    async def ensure_character_anchor(
        self,
        character_id: str,
        *,
        reference_slot: str = "avatar_front_url",
        seed: int | None = None,
        force: bool = False,
    ) -> CharacterAnchorRow:
        _validate_slot(reference_slot, CHARACTER_REFERENCE_SLOTS)
        character = self.db.query(Character).filter(Character.id == character_id).first()
        if not character:
            raise ValueError(f"Character not found: {character_id}")

        anchor = self._character_anchor(character.id, reference_slot)
        prompt = _character_base_prompt(character)
        if anchor is None:
            anchor = CharacterAnchorRow(character_id=character.id, reference_slot=reference_slot)
            self.db.add(anchor)
            self.db.flush()

        current_url = getattr(character, reference_slot)
        if force or not reference_url_is_usable(current_url):
            current_url = await generate_reference_url(
                self.db,
                prompt,
                destination_role="character_anchor_image",
                destination_context={
                    "asset_type": "character",
                    "asset_id": character.id,
                    "anchor_kind": "character_anchor",
                    "slot": reference_slot,
                },
            )
            setattr(character, reference_slot, current_url)

        resolved_seed = _resolve_seed(seed, anchor.seed, f"character:{character.id}:{reference_slot}:{prompt}")
        anchor.name = character.name
        anchor.base_prompt = prompt
        anchor.anchor_image_url = current_url
        anchor.seed = resolved_seed
        anchor.ref_mode = CHARACTER_SLOT_REF_MODES[reference_slot]
        anchor.status = AnchorStatus.LOCKED.value if current_url else AnchorStatus.DRAFT.value
        anchor.provider_options_json = {"seed": resolved_seed}
        anchor.metadata_json = {"source": "asset_anchor_manager"}
        self.db.commit()
        self.db.refresh(anchor)
        return anchor

    async def ensure_scene_anchor(
        self,
        scene_id: str,
        *,
        reference_slot: str = "reference_wideshot_url",
        seed: int | None = None,
        force: bool = False,
    ) -> SceneAnchorRow:
        _validate_slot(reference_slot, SCENE_REFERENCE_SLOTS)
        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise ValueError(f"Scene not found: {scene_id}")

        anchor = self._scene_anchor(scene.id, reference_slot)
        prompt = _scene_environment_prompt(scene)
        if anchor is None:
            anchor = SceneAnchorRow(scene_id=scene.id, reference_slot=reference_slot)
            self.db.add(anchor)
            self.db.flush()

        current_url = getattr(scene, reference_slot)
        if force or not reference_url_is_usable(current_url):
            current_url = await generate_reference_url(
                self.db,
                _scene_reference_image_prompt(scene),
                destination_role="scene_reference_image",
                destination_context={
                    "asset_type": "scene",
                    "asset_id": scene.id,
                    "anchor_kind": "scene_anchor",
                    "slot": reference_slot,
                },
            )
            setattr(scene, reference_slot, current_url)

        resolved_seed = _resolve_seed(seed, anchor.seed, f"scene:{scene.id}:{reference_slot}:{prompt}")
        anchor.scene_name = scene.name
        anchor.environment_prompt = prompt
        anchor.anchor_image_url = current_url
        anchor.seed = resolved_seed
        anchor.ref_mode = SCENE_SLOT_REF_MODES[reference_slot]
        anchor.status = AnchorStatus.LOCKED.value if current_url else AnchorStatus.DRAFT.value
        anchor.provider_options_json = {"seed": resolved_seed}
        anchor.metadata_json = {"source": "asset_anchor_manager"}
        self.db.commit()
        self.db.refresh(anchor)
        return anchor

    def adapt_provider_parameters(
        self,
        *,
        character_anchors: Sequence[CharacterAnchorRow] = (),
        scene_anchor: SceneAnchorRow | None = None,
        provider: str,
        provider_options_schema: dict[str, Any] | None = None,
    ) -> AnchorProviderPayload:
        references: list[dict[str, Any]] = []
        priority = 1
        seed = None
        for anchor in character_anchors:
            if not _usable_anchor_url(anchor.anchor_image_url):
                continue
            seed = seed if seed is not None else anchor.seed
            references.append(_reference_image(
                url=anchor.anchor_image_url,
                role=REFERENCE_CHARACTER_ANCHOR,
                asset_type="character",
                asset_id=anchor.character_id,
                name=anchor.name,
                anchor_id=anchor.id,
                slot=anchor.reference_slot,
                ref_mode=anchor.ref_mode,
                provider=provider,
                priority=priority,
            ))
            priority += 1
        if scene_anchor and _usable_anchor_url(scene_anchor.anchor_image_url):
            seed = seed if seed is not None else scene_anchor.seed
            references.append(_reference_image(
                url=scene_anchor.anchor_image_url,
                role=REFERENCE_SCENE_REFERENCE,
                asset_type="scene",
                asset_id=scene_anchor.scene_id,
                name=scene_anchor.scene_name,
                anchor_id=scene_anchor.id,
                slot=scene_anchor.reference_slot,
                ref_mode=scene_anchor.ref_mode,
                provider=provider,
                priority=priority,
            ))

        provider_options = {}
        if seed is not None and _schema_allows_seed(provider_options_schema):
            provider_options["seed"] = int(seed)
        primary_reference = references[0] if references else {}
        return AnchorProviderPayload(
            reference_images=references,
            provider_options=provider_options,
            ref_image_url=primary_reference.get("ref_image_url"),
            ref_mode=primary_reference.get("ref_mode"),
            seed=seed,
        )

    def latest_character_anchors(self, character_ids: Sequence[str]) -> list[CharacterAnchorRow]:
        anchors = []
        for character_id in character_ids:
            anchor = (
                self.db.query(CharacterAnchorRow)
                .filter(CharacterAnchorRow.character_id == character_id)
                .filter(CharacterAnchorRow.status == AnchorStatus.LOCKED.value)
                .order_by(CharacterAnchorRow.updated_at.desc(), CharacterAnchorRow.created_at.desc())
                .first()
            )
            if anchor:
                anchors.append(anchor)
        return anchors

    def latest_scene_anchor(self, scene_id: str | None) -> SceneAnchorRow | None:
        if not scene_id:
            return None
        return (
            self.db.query(SceneAnchorRow)
            .filter(SceneAnchorRow.scene_id == scene_id)
            .filter(SceneAnchorRow.status == AnchorStatus.LOCKED.value)
            .order_by(SceneAnchorRow.updated_at.desc(), SceneAnchorRow.created_at.desc())
            .first()
        )

    def _character_anchor(self, character_id: str, reference_slot: str) -> CharacterAnchorRow | None:
        return (
            self.db.query(CharacterAnchorRow)
            .filter(CharacterAnchorRow.character_id == character_id)
            .filter(CharacterAnchorRow.reference_slot == reference_slot)
            .first()
        )

    def _scene_anchor(self, scene_id: str, reference_slot: str) -> SceneAnchorRow | None:
        return (
            self.db.query(SceneAnchorRow)
            .filter(SceneAnchorRow.scene_id == scene_id)
            .filter(SceneAnchorRow.reference_slot == reference_slot)
            .first()
        )


def _validate_slot(slot: str, available_slots: tuple[tuple[str, str], ...]) -> None:
    valid = {field for field, _label in available_slots}
    if slot not in valid:
        raise ValueError(f"Invalid anchor reference slot: {slot}")


def _character_base_prompt(character: Character) -> str:
    return " ".join(part for part in [
        f"Character anchor for {character.name}.",
        f"Role: {character.role_type}.",
        f"Gender: {character.gender}.",
        f"Age: {character.age_range}." if character.age_range else "",
        f"Personality: {character.personality}." if character.personality else "",
        f"Appearance: {character.appearance_desc}." if character.appearance_desc else "",
        f"Outfit: {character.outfit_desc}." if character.outfit_desc else "",
        "Keep face, hairstyle, body proportion, and clothing consistent across every shot.",
    ] if part).strip()


def _scene_environment_prompt(scene: Scene) -> str:
    return " ".join(part for part in [
        f"Scene anchor for {scene.name}.",
        f"Type: {scene.scene_type}.",
        f"Location: {scene.location_desc}." if scene.location_desc else "",
        f"Lighting: {scene.lighting}." if scene.lighting else "",
        f"Mood: {scene.mood}." if scene.mood else "",
        "Keep environment layout, palette, props, and lighting consistent across every shot.",
    ] if part).strip()


def _scene_reference_image_prompt(scene: Scene) -> str:
    return f"{_scene_environment_prompt(scene)} {SCENE_EMPTY_PLATE_INSTRUCTION}"


def _resolve_seed(requested: int | None, existing: int | None, stable_key: str) -> int:
    for value in (requested, existing):
        if value is not None:
            return _clamp_seed(value)
    digest = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (MAX_PROVIDER_SEED + 1)


def _clamp_seed(value: int) -> int:
    return max(0, min(int(value), MAX_PROVIDER_SEED))


def _schema_allows_seed(provider_options_schema: dict[str, Any] | None) -> bool:
    schema = provider_options_schema or {}
    if "seed" in schema:
        return True
    config = schema.get("config") if isinstance(schema.get("config"), dict) else {}
    nested = config.get("provider_options_schema") if isinstance(config.get("provider_options_schema"), dict) else {}
    return "seed" in nested


def _usable_anchor_url(value: str | None) -> bool:
    return reference_url_is_usable(value)


def _reference_image(**kwargs) -> dict[str, Any]:
    kwargs["ref_image_url"] = kwargs["url"]
    return AnchorReferenceImage(**kwargs).model_dump(mode="json", exclude_none=True)
