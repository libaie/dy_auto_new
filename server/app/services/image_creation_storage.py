from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import UploadFile


IMAGE_CREATION_ROOT = Path(__file__).resolve().parents[1] / "static" / "image-creation"
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/gif",
}
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
_CONTENT_TYPE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/gif": ".gif",
}


def ensure_storage_dirs() -> None:
    for name in ("uploads", "outputs", "thumbs"):
        (IMAGE_CREATION_ROOT / name).mkdir(parents=True, exist_ok=True)


def _suffix_for(content_type: str | None, source_url: str = "") -> str:
    suffix = Path(urlparse(source_url or "").path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return _CONTENT_TYPE_SUFFIXES.get(content_type or "", ".png")


async def save_upload(file: UploadFile, public_base_url: str) -> dict:
    ensure_storage_dirs()
    content = await file.read()
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("SOURCE_IMAGE_UNSUPPORTED_TYPE")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("SOURCE_IMAGE_TOO_LARGE")

    digest = hashlib.sha256(content).hexdigest()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}:
        suffix = _CONTENT_TYPE_SUFFIXES[file.content_type]
    local_path = IMAGE_CREATION_ROOT / "uploads" / f"{digest}{suffix}"
    local_path.write_bytes(content)
    return {
        "url": f"{public_base_url.rstrip('/')}/static/image-creation/uploads/{local_path.name}",
        "local_path": str(local_path),
        "storage_path": f"uploads/{local_path.name}",
        "checksum": digest,
        "size_bytes": len(content),
    }


def save_output_bytes(content: bytes, public_base_url: str, content_type: str | None = None, source_url: str = "") -> dict:
    ensure_storage_dirs()
    clean_content_type = (content_type or "").split(";")[0].strip().lower()
    if clean_content_type and clean_content_type not in ALLOWED_CONTENT_TYPES and clean_content_type != "application/octet-stream":
        raise ValueError("OUTPUT_IMAGE_UNSUPPORTED_TYPE")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("OUTPUT_IMAGE_TOO_LARGE")

    digest = hashlib.sha256(content).hexdigest()
    suffix = _suffix_for(clean_content_type, source_url)
    local_path = IMAGE_CREATION_ROOT / "outputs" / f"{digest}{suffix}"
    local_path.write_bytes(content)
    return {
        "url": f"{public_base_url.rstrip('/')}/static/image-creation/outputs/{local_path.name}",
        "local_path": str(local_path),
        "storage_path": f"outputs/{local_path.name}",
        "checksum": digest,
        "size_bytes": len(content),
        "mime_type": clean_content_type if clean_content_type in ALLOWED_CONTENT_TYPES else None,
    }


def configured_public_base_url() -> str:
    return os.getenv("DY_AUTO_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
