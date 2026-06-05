"""Reference image generation for characters and scenes."""
import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import bj_now
from app.db_models import Character, ImageCreationAsset, ImageCreationTask, Scene, Series, series_characters, series_scenes
from app.services.image_creation_storage import configured_public_base_url
from app.services.visual_style_inference_service import (
    append_visual_style_constraints,
    infer_visual_style_from_story,
    reference_prompt_matches_visual_style,
)


class ReferenceAssetError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


CHARACTER_REFERENCE_SLOTS = (
    ("avatar_front_url", "front-view character anchor sheet"),
    ("avatar_side_url", "side-profile character anchor sheet"),
    ("avatar_threequarter_url", "three-quarter character anchor sheet"),
    ("avatar_fullbody_url", "full-body costume and proportions anchor sheet"),
)

SCENE_REFERENCE_SLOTS = (
    ("reference_wideshot_url", "wide establishing scene reference"),
    ("reference_midshot_url", "mid-shot scene lighting reference"),
    ("reference_aerial_url", "high-angle environment layout reference"),
)

USABLE_REFERENCE_ASSET_STATUSES = {"generated", "review_pending", "approved"}
FAILED_REFERENCE_TASK_STATUSES = {"failed", "blocked", "rejected", "error"}
IN_PROGRESS_REFERENCE_TASK_STATUSES = {"pending", "queued", "submitted", "running"}
REFERENCE_SYNC_POLL_ATTEMPTS = 60
REFERENCE_SYNC_POLL_DELAY_SECONDS = 2.0
PROJECT_MANAGED_REFERENCE_PREFIXES = ("/static/image-creation/", "/api/image-creation/pixelle-files/")


def _tos_signed_url_expires_at(value: str) -> datetime | None:
    parsed = urlparse(str(value or "").strip())
    query = {key.lower(): values for key, values in parse_qs(parsed.query).items()}
    date_values = query.get("x-tos-date")
    expires_values = query.get("x-tos-expires")
    if not date_values or not expires_values:
        return None
    try:
        issued_at = datetime.strptime(date_values[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        expires_seconds = int(expires_values[0])
    except (TypeError, ValueError):
        return None
    return issued_at + timedelta(seconds=expires_seconds)


def reference_url_is_usable(value: str | None, *, now: datetime | None = None) -> bool:
    clean = str(value or "").strip()
    if not clean:
        return False
    expires_at = _tos_signed_url_expires_at(clean)
    if not expires_at:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current < expires_at


def _reference_url_needs_project_copy(value: str | None) -> bool:
    clean = str(value or "").strip()
    if not clean:
        return False
    if any(clean.startswith(prefix) for prefix in PROJECT_MANAGED_REFERENCE_PREFIXES):
        return False
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    public_base = urlparse(configured_public_base_url())
    if (
        parsed.scheme == public_base.scheme
        and parsed.netloc == public_base.netloc
        and any(parsed.path.startswith(prefix) for prefix in PROJECT_MANAGED_REFERENCE_PREFIXES)
    ):
        return False
    return True


async def _ensure_project_reference_asset(db: Session, asset: ImageCreationAsset) -> ImageCreationAsset:
    if not asset.url or not _reference_url_needs_project_copy(asset.url):
        return asset
    from app.services.image_creation_service import _copy_external_image

    source_url = asset.url
    try:
        saved = await _copy_external_image(source_url)
    except (httpx.HTTPError, HTTPException, OSError, ValueError) as exc:
        raise ReferenceAssetError(
            "REFERENCE_PROVIDER_PERSIST_FAILED",
            f"Reference image could not be saved into project storage: {exc}",
            {"image_asset_id": asset.id, "source_url": source_url},
        ) from exc

    asset.source_url = asset.source_url or source_url
    asset.url = saved["url"]
    asset.local_path = saved.get("local_path") or asset.local_path
    asset.storage_path = saved.get("storage_path") or asset.storage_path
    asset.checksum = saved.get("checksum") or asset.checksum
    asset.size_bytes = saved.get("size_bytes") or asset.size_bytes
    asset.mime_type = saved.get("mime_type") or asset.mime_type
    asset.storage_status = "persisted"
    db.commit()
    db.refresh(asset)
    return asset


def _slot_fields(slots: tuple[tuple[str, str], ...]) -> set[str]:
    return {field for field, _label in slots}


def _reference_idempotency_key(destination_role: str, prompt: str, destination_context: dict | None) -> str:
    context_hash = hashlib.sha256(repr(sorted((destination_context or {}).items())).encode("utf-8")).hexdigest()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return f"reference:{destination_role}:{context_hash[:16]}:{prompt_hash}"


def _json_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _image_task_error(exc: HTTPException, scene_key: str) -> ReferenceAssetError:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    provider_code = detail.get("error_code") or detail.get("code") or "REFERENCE_PROVIDER_REQUEST_FAILED"
    message = detail.get("message") or "Reference image provider request failed"
    if provider_code in {"IMAGE_CAPABILITY_UNSUPPORTED", "MODEL_SCENE_NOT_CONFIGURED"}:
        return ReferenceAssetError(
            "MODEL_SCENE_NOT_CONFIGURED",
            message,
            {"scene_key": scene_key, "capability": "text_to_image", "provider_code": provider_code},
        )
    return ReferenceAssetError(
        "REFERENCE_PROVIDER_REQUEST_FAILED",
        message,
        {"provider_code": provider_code, "status_code": exc.status_code, "detail": detail},
    )


def _raise_failed_reference_task(task) -> None:
    if task.status in FAILED_REFERENCE_TASK_STATUSES or task.error_code:
        raise ReferenceAssetError(
            "REFERENCE_PROVIDER_REQUEST_FAILED",
            task.error_message or "Reference image task failed before producing a usable image.",
            {
                "image_task_id": task.id,
                "status": task.status,
                "error_code": task.error_code,
                "error_message": task.error_message,
            },
        )


def _latest_reference_asset(db: Session, task_id: str) -> ImageCreationAsset | None:
    assets = (
        db.query(ImageCreationAsset)
        .filter(ImageCreationAsset.task_id == task_id)
        .filter(ImageCreationAsset.status.in_(USABLE_REFERENCE_ASSET_STATUSES))
        .filter(ImageCreationAsset.url.isnot(None))
        .order_by(ImageCreationAsset.is_latest.desc(), ImageCreationAsset.version.desc(), ImageCreationAsset.created_at.desc())
        .limit(10)
        .all()
    )
    return next((asset for asset in assets if reference_url_is_usable(asset.url)), None)


def _task_matches_reference_destination(
    task: ImageCreationTask,
    destination_role: str,
    destination_context: dict | None,
) -> bool:
    expected = destination_context or {}
    if not expected or task.destination_role != destination_role:
        return False
    return _json_dict(task.destination_context_json) == expected


def _find_reusable_reference_task(
    db: Session,
    destination_role: str,
    destination_context: dict | None,
) -> ImageCreationTask | None:
    if not destination_context:
        return None
    candidates = (
        db.query(ImageCreationTask)
        .filter(ImageCreationTask.destination_role == destination_role)
        .order_by(ImageCreationTask.updated_at.desc(), ImageCreationTask.created_at.desc())
        .limit(50)
        .all()
    )
    for task in candidates:
        if not _task_matches_reference_destination(task, destination_role, destination_context):
            continue
        if _latest_reference_asset(db, task.id):
            return task
        if task.status in IN_PROGRESS_REFERENCE_TASK_STATUSES and (task.pixelle_task_id or task.provider_task_id):
            return task
    return None


async def _sync_reference_task_until_asset_ready(db: Session, task, sync_image_task):
    for attempt in range(max(1, REFERENCE_SYNC_POLL_ATTEMPTS)):
        task = await sync_image_task(db, task.id)
        _raise_failed_reference_task(task)
        if _latest_reference_asset(db, task.id):
            return task
        if str(task.status or "").lower() not in IN_PROGRESS_REFERENCE_TASK_STATUSES:
            return task
        if attempt < REFERENCE_SYNC_POLL_ATTEMPTS - 1 and REFERENCE_SYNC_POLL_DELAY_SECONDS > 0:
            await asyncio.sleep(REFERENCE_SYNC_POLL_DELAY_SECONDS)
    return task


async def generate_reference_url(
    db: Session,
    prompt: str,
    scene_key: str = "image_generation",
    destination_role: str = "style_reference_image",
    destination_context: dict | None = None,
) -> str:
    from app.services.image_creation_service import create_image_task, sync_image_task

    payload = {
        "mode": "text_to_image",
        "prompt": prompt,
        "count": 1,
        "destination_role": destination_role,
        "destination_context": destination_context or {},
        "idempotency_key": _reference_idempotency_key(destination_role, prompt, destination_context),
        "cost_confirmation": True,
    }
    task = _find_reusable_reference_task(db, destination_role, destination_context)
    if not task:
        try:
            task = await create_image_task(db, payload)
        except HTTPException as exc:
            raise _image_task_error(exc, scene_key) from exc

    _raise_failed_reference_task(task)
    has_provider_id = bool(task.pixelle_task_id or task.provider_task_id)
    if has_provider_id:
        try:
            task = await _sync_reference_task_until_asset_ready(db, task, sync_image_task)
        except HTTPException as exc:
            raise _image_task_error(exc, scene_key) from exc
        _raise_failed_reference_task(task)

    image_asset = _latest_reference_asset(db, task.id)
    if not image_asset or not image_asset.url:
        raise ReferenceAssetError(
            "REFERENCE_PROVIDER_EMPTY_RESULT",
            "Reference image provider returned no image URL",
            {"image_task_id": task.id, "status": task.status, "scene_key": scene_key},
        )
    image_asset = await _ensure_project_reference_asset(db, image_asset)
    return image_asset.url


def _series_text_for_character(db: Session, character_id: str) -> str:
    series = (
        db.query(Series)
        .join(series_characters, Series.id == series_characters.c.series_id)
        .filter(series_characters.c.character_id == character_id)
        .order_by(Series.updated_at.desc(), Series.id.asc())
        .first()
    )
    if not series:
        return ""
    return f"{series.title or ''} {series.logline or ''} {series.genre or ''} {series.story_bible_json or {}}"


def _series_text_for_scene(db: Session, scene_id: str) -> str:
    series = (
        db.query(Series)
        .join(series_scenes, Series.id == series_scenes.c.series_id)
        .filter(series_scenes.c.scene_id == scene_id)
        .order_by(Series.updated_at.desc(), Series.id.asc())
        .first()
    )
    if not series:
        return ""
    return f"{series.title or ''} {series.logline or ''} {series.genre or ''} {series.story_bible_json or {}}"


def _character_prompt(character: Character, label: str, visual_style: dict | None = None) -> str:
    prompt = (
        f"{label}, clear face, hairstyle, outfit, stable identity, consistent series style. "
        f"Name: {character.name}. Role: {character.role_type}. Gender: {character.gender}. "
        f"Age: {character.age_range or ''}. Personality: {character.personality or ''}. "
        f"Appearance: {character.appearance_desc or ''}. Outfit: {character.outfit_desc or ''}."
    )
    return append_visual_style_constraints(prompt, visual_style)


def _scene_prompt(scene: Scene, label: str, visual_style: dict | None = None) -> str:
    prompt = (
        f"{label}, consistent palette, lighting, environment design, and series style. "
        f"Scene: {scene.name}. Type: {scene.scene_type}. Location: {scene.location_desc or ''}. "
        f"Lighting: {scene.lighting or ''}. Mood: {scene.mood or ''}."
    )
    return append_visual_style_constraints(prompt, visual_style)


def _stored_reference_prompt_matches(row, slot: str, visual_style: dict | None) -> bool:
    meta_json = row.meta_json or {}
    reference_generation = meta_json.get("reference_generation") if isinstance(meta_json, dict) else {}
    slot_meta = reference_generation.get(slot) if isinstance(reference_generation, dict) else {}
    stored_prompt = slot_meta.get("prompt") if isinstance(slot_meta, dict) else None
    return reference_prompt_matches_visual_style(stored_prompt, visual_style)


def _target_slots(row, requested_slot: str, slots: tuple[tuple[str, str], ...], visual_style: dict | None = None) -> list[tuple[str, str]]:
    if requested_slot == "all":
        return [
            (field, label)
            for field, label in slots
            if not reference_url_is_usable(getattr(row, field))
            or not _stored_reference_prompt_matches(row, field, visual_style)
        ]
    valid_slots = _slot_fields(slots)
    if requested_slot not in valid_slots:
        raise ReferenceAssetError(
            "REFERENCE_SLOT_INVALID",
            f"Invalid reference slot: {requested_slot}",
            {"slot": requested_slot, "valid_slots": sorted(valid_slots) + ["all"]},
        )
    label_by_field = dict(slots)
    return [(requested_slot, label_by_field[requested_slot])]


def _record_generation(row, slot: str, prompt: str, url: str) -> None:
    meta_json = dict(row.meta_json or {})
    reference_generation = dict(meta_json.get("reference_generation") or {})
    reference_generation[slot] = {
        "prompt": prompt,
        "url": url,
        "generated_at": bj_now().isoformat(),
    }
    meta_json["reference_generation"] = reference_generation
    row.meta_json = meta_json
    flag_modified(row, "meta_json")


def _to_dict(row) -> dict:
    return {col.name: getattr(row, col.name) for col in row.__table__.columns}


async def generate_character_reference_images(db: Session, character_id: str, slot: str = "all") -> dict:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise ReferenceAssetError("CHARACTER_NOT_FOUND", "Character not found", {"character_id": character_id})

    visual_style = infer_visual_style_from_story(
        _series_text_for_character(db, character.id),
        character.name,
        character.role_type,
        character.age_range,
        character.personality,
        character.appearance_desc,
        character.outfit_desc,
    )
    targets = _target_slots(character, slot, CHARACTER_REFERENCE_SLOTS, visual_style)
    generated: list[dict] = []
    for field, label in targets:
        prompt = _character_prompt(character, label, visual_style)
        url = await generate_reference_url(
            db,
            prompt,
            destination_role="character_anchor_image",
            destination_context={"asset_type": "character", "asset_id": character.id, "slot": field},
        )
        setattr(character, field, url)
        _record_generation(character, field, prompt, url)
        generated.append({"slot": field, "url": url})

    db.commit()
    db.refresh(character)
    return {
        "ok": True,
        "character": _to_dict(character),
        "generated": generated,
        "missing_assets": [],
        "warnings": [],
        "missing_requirements": [],
    }


async def generate_scene_reference_images(db: Session, scene_id: str, slot: str = "all") -> dict:
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise ReferenceAssetError("SCENE_NOT_FOUND", "Scene not found", {"scene_id": scene_id})

    visual_style = infer_visual_style_from_story(
        _series_text_for_scene(db, scene.id),
        scene.name,
        scene.scene_type,
        scene.location_desc,
        scene.lighting,
        scene.mood,
    )
    targets = _target_slots(scene, slot, SCENE_REFERENCE_SLOTS, visual_style)
    generated: list[dict] = []
    for field, label in targets:
        prompt = _scene_prompt(scene, label, visual_style)
        url = await generate_reference_url(
            db,
            prompt,
            destination_role="scene_reference_image",
            destination_context={"asset_type": "scene", "asset_id": scene.id, "slot": field},
        )
        setattr(scene, field, url)
        _record_generation(scene, field, prompt, url)
        generated.append({"slot": field, "url": url})

    db.commit()
    db.refresh(scene)
    return {
        "ok": True,
        "scene": _to_dict(scene),
        "generated": generated,
        "missing_assets": [],
        "warnings": [],
        "missing_requirements": [],
    }
