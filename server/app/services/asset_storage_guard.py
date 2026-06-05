from __future__ import annotations

import hashlib
import ipaddress
import shutil
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import bj_now
from app.db_models import VideoProductionAsset
from app.services.production_errors import ProductionErrorCode, ProductionRepairableError

ALLOWED_PROVIDER_SCHEMES = {"https"}
ALLOWED_IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"RIFF")
ALLOWED_VIDEO_MAGIC = (b"\x00\x00\x00", b"ftyp")


def _storage_failed(asset: VideoProductionAsset, cause: str, message: str) -> ProductionRepairableError:
    return ProductionRepairableError(
        code=ProductionErrorCode.ASSET_STORAGE_FAILED,
        message=message,
        cause=cause,
        repair_action="Retry asset persistence or regenerate the asset.",
        repair_route=f"/video-production/{asset.run_id}",
        affected_ids=[asset.id],
        retryable=True,
    )


def _mark_storage_failed(db: Session, asset: VideoProductionAsset, error: ProductionRepairableError) -> None:
    asset.copy_status = "storage_failed"
    asset.status = "storage_failed"
    asset.storage_error_json = {
        "code": error.code.value,
        "cause": error.cause,
        "message": error.message,
    }
    asset.updated_at = bj_now()
    db.commit()


def _is_private_or_local_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    host = hostname.strip().lower().strip("[]")
    if host in {"localhost"} or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified


def _validate_provider_url(asset: VideoProductionAsset) -> str:
    source_url = asset.source_url or asset.url or ""
    parsed = urlparse(source_url)
    if parsed.scheme not in ALLOWED_PROVIDER_SCHEMES:
        raise _storage_failed(asset, "unsupported_source_url", "Asset source URL scheme is not allowed.")
    if _is_private_or_local_host(parsed.hostname):
        raise _storage_failed(asset, "local_source_url", "Asset source URL cannot point to a local or private host.")
    return source_url


def _safe_source_from_local(asset: VideoProductionAsset, pixelle_output_root: Path) -> Path:
    source = Path(asset.local_path or "").resolve()
    root = pixelle_output_root.resolve()
    if source != root and root not in source.parents:
        raise _storage_failed(asset, "pixelle_path_outside_root", "Pixelle output path is outside the allowed root.")
    if not source.exists() or not source.is_file():
        raise _storage_failed(asset, "source_file_missing", "Asset file does not exist.")
    return source


def _looks_like_expected_asset(asset: VideoProductionAsset, path: Path) -> bool:
    head = path.read_bytes()[:16]
    if asset.asset_type == "image":
        return any(head.startswith(item) for item in ALLOWED_IMAGE_MAGIC)
    if asset.asset_type in {"video_segment", "final_video"}:
        return any(item in head for item in ALLOWED_VIDEO_MAGIC) or path.suffix.lower() in {".mp4", ".mov", ".webm"}
    return True


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_provider_url(asset: VideoProductionAsset, target: Path) -> None:
    source_url = _validate_provider_url(asset)
    try:
        with httpx.stream("GET", source_url, follow_redirects=False, timeout=30.0) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        raise _storage_failed(asset, "remote_download_failed", "Provider asset download failed.") from exc


def persist_provider_asset(
    db: Session,
    asset_id: str,
    *,
    output_root: str | Path,
    pixelle_output_root: str | Path | None = None,
) -> VideoProductionAsset:
    asset = db.query(VideoProductionAsset).filter_by(id=asset_id).one()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(asset.source_url or asset.url or "").path).suffix
    if asset.local_path:
        local_parsed = urlparse(asset.local_path)
        local_suffix = Path(local_parsed.path if local_parsed.scheme in {"http", "https"} else asset.local_path).suffix
        suffix = local_suffix or suffix
    suffix = suffix or (".png" if asset.asset_type == "image" else ".mp4")
    tmp_path = output_root / f"{asset.id}.tmp{suffix}"
    final_path = output_root / f"{asset.id}{suffix}"

    try:
        local_scheme = urlparse(asset.local_path or "").scheme
        if asset.local_path and local_scheme not in {"http", "https"}:
            source = _safe_source_from_local(asset, Path(pixelle_output_root or output_root))
            shutil.copyfile(source, tmp_path)
        else:
            _download_provider_url(asset, tmp_path)

        if not _looks_like_expected_asset(asset, tmp_path):
            raise _storage_failed(asset, "mime_type_mismatch", "Asset content does not match the expected type.")

        checksum = _checksum(tmp_path)
        tmp_path.replace(final_path)
        asset.storage_path = str(final_path)
        asset.local_path = str(final_path)
        asset.url = str(final_path)
        asset.checksum = checksum
        asset.size_bytes = final_path.stat().st_size
        asset.copy_status = "persisted"
        asset.status = "review_pending"
        asset.storage_error_json = {}
        asset.updated_at = bj_now()
        db.commit()
        db.refresh(asset)
        return asset
    except ProductionRepairableError as exc:
        tmp_path.unlink(missing_ok=True)
        _mark_storage_failed(db, asset, exc)
        raise
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        error = _storage_failed(asset, "copy_failed", "Asset persistence failed.")
        _mark_storage_failed(db, asset, error)
        raise error from exc
