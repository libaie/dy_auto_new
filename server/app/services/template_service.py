"""Template image storage — listing, caching, and file operations."""
import hashlib
import os
from pathlib import Path
from typing import Optional

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template_images"
TEMPLATE_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class TemplateService:
    """Template image management with MD5 caching."""

    def __init__(self):
        # filename -> { md5, mtime, size }
        self._md5_cache: dict[str, dict] = {}

    def list_templates(self) -> list[dict]:
        """List all template images with metadata. MD5 is cached by mtime."""
        templates = []
        if not TEMPLATE_DIR.is_dir():
            return templates
        for f in sorted(TEMPLATE_DIR.iterdir()):
            if f.suffix.lower() in ALLOWED_EXTENSIONS and f.is_file():
                stat = f.stat()
                cached = self._md5_cache.get(f.name)
                if cached and cached["mtime"] == stat.st_mtime and cached["size"] == stat.st_size:
                    md5 = cached["md5"]
                else:
                    md5 = hashlib.md5(f.read_bytes()).hexdigest()
                    self._md5_cache[f.name] = {
                        "md5": md5,
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                    }
                templates.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "md5": md5,
                })
        return templates

    def get_template_path(self, filename: str) -> Optional[Path]:
        """Get the full path to a template file. Returns None if not found or path traversal detected."""
        filepath = TEMPLATE_DIR / filename
        if not filepath.exists():
            return None
        if filepath.resolve().parent != TEMPLATE_DIR.resolve():
            return None
        return filepath

    def delete_template(self, filename: str) -> bool:
        """Delete a template file. Returns True if deleted, False if not found."""
        filepath = self.get_template_path(filename)
        if not filepath:
            return False
        filepath.unlink()
        self._md5_cache.pop(filename, None)
        return True

    def save_template(self, filename: str, content: bytes) -> Path:
        """Save template content to disk. Returns the saved path."""
        dest = TEMPLATE_DIR / filename
        dest.write_bytes(content)
        # Invalidate cache for this file
        self._md5_cache.pop(filename, None)
        return dest


template_service = TemplateService()
