"""选择器管理业务域模块。

选择器管理业务域，负责 UI 选择器模板、版本和设备端匹配配置。本文件负责 template_service 相关业务规则、状态转换和外部系统边界。
"""

import hashlib
import os
from pathlib import Path
from typing import Optional

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template_images"
TEMPLATE_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _aspect_tag(resolution: str) -> str:
    """业务函数：处理 _aspect_tag 对应的业务流程、校验或数据转换。"""
    """Compute aspect-ratio tag from 'WxH' string, e.g. '1080x2400' → '9:20'."""
    try:
        w, h = resolution.split("x")
        w, h = int(w), int(h)
    except (ValueError, AttributeError):
        return "unknown"
    if w == 0 or h == 0:
        return "unknown"
    a, b = w, h
    while b:
        a, b = b, a % b
    gcd = a
    return f"{w // gcd}:{h // gcd}"


def _same_aspect_dirs(resolution: str) -> list[Path]:
    """业务函数：处理 _same_aspect_dirs 对应的业务流程、校验或数据转换。"""
    """Return all resolution subdirectories with the same aspect ratio as `resolution`."""
    target_ar = _aspect_tag(resolution)
    if target_ar == "unknown":
        return []
    result = []
    try:
        for d in TEMPLATE_DIR.iterdir():
            if d.is_dir() and d.name != "default" and d.name != resolution:
                if _aspect_tag(d.name) == target_ar:
                    result.append(d)
    except OSError:
        pass
    return result


def _ensure_resolution_dir(resolution: str) -> Path:
    """业务函数：处理 _ensure_resolution_dir 对应的业务流程、校验或数据转换。"""
    """Ensure a resolution subdirectory exists."""
    d = TEMPLATE_DIR / resolution
    d.mkdir(exist_ok=True)
    return d


def _safe_resolve(path: Path, parent: Path) -> bool:
    """业务函数：处理 _safe_resolve 对应的业务流程、校验或数据转换。"""
    """Check that resolved path is within parent directory."""
    try:
        return path.resolve().parent == parent.resolve()
    except Exception:
        return False


class TemplateService:
    """业务类：承载 TemplateService 相关的数据结构、状态或业务协作。"""
    """Template image management with MD5 caching and resolution subdirectories."""

    def __init__(self):
        # cache key: "resolution/filename" → { md5, mtime, size }
        """初始化业务对象依赖，保存后续流程需要的运行上下文。"""
        self._md5_cache: dict[str, dict] = {}

    def _iter_templates(self, resolution: str = None):
        """业务函数：处理 _iter_templates 对应的业务流程、校验或数据转换。"""
        """Iterate template files. If resolution given, includes that subdirectory,
        same-aspect-ratio directories, plus 'default' as fallback.
        Otherwise iterates all resolution subdirectories."""
        if resolution:
            dirs = [TEMPLATE_DIR / resolution]
            dirs.extend(_same_aspect_dirs(resolution))
            dirs.append(TEMPLATE_DIR / "default")
        else:
            dirs = [d for d in TEMPLATE_DIR.iterdir() if d.is_dir()]
        seen = set()
        for subdir in dirs:
            if not subdir.is_dir():
                continue
            for f in sorted(subdir.iterdir()):
                if f.suffix.lower() in ALLOWED_EXTENSIONS and f.is_file():
                    if f.name not in seen:
                        seen.add(f.name)
                        yield f, subdir.name

    def list_templates(self, resolution: str = None) -> list[dict]:
        """业务函数：处理 list_templates 对应的业务流程、校验或数据转换。"""
        """List template images with metadata. Optionally filter by resolution."""
        templates = []
        for f, res in self._iter_templates(resolution):
            stat = f.stat()
            cache_key = f"{res}/{f.name}"
            cached = self._md5_cache.get(cache_key)
            if cached and cached["mtime"] == stat.st_mtime and cached["size"] == stat.st_size:
                md5 = cached["md5"]
            else:
                md5 = hashlib.md5(f.read_bytes()).hexdigest()
                self._md5_cache[cache_key] = {
                    "md5": md5,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                }
            templates.append({
                "filename": f.name,
                "size": stat.st_size,
                "md5": md5,
                "resolution": res,
            })
        return templates

    def get_template_path(self, filename: str, resolution: str = "default") -> Optional[Path]:
        """业务函数：处理 get_template_path 对应的业务流程、校验或数据转换。"""
        """Get template file path. Looks in resolution subdirectory first, then 'default' fallback."""
        # Try resolution-specific first
        if resolution:
            filepath = TEMPLATE_DIR / resolution / filename
            if filepath.exists() and _safe_resolve(filepath, TEMPLATE_DIR / resolution):
                return filepath
        # Fall back to default
        filepath = TEMPLATE_DIR / "default" / filename
        if filepath.exists() and _safe_resolve(filepath, TEMPLATE_DIR / "default"):
            return filepath
        return None

    def delete_template(self, filename: str, resolution: str = "default") -> bool:
        """业务函数：处理 delete_template 对应的业务流程、校验或数据转换。"""
        """Delete a template file."""
        filepath = TEMPLATE_DIR / resolution / filename
        if not filepath.exists():
            return False
        if not _safe_resolve(filepath, TEMPLATE_DIR / resolution):
            return False
        filepath.unlink()
        self._md5_cache.pop(f"{resolution}/{filename}", None)
        return True

    def save_template(self, filename: str, content: bytes, resolution: str = "default") -> Path:
        """业务函数：处理 save_template 对应的业务流程、校验或数据转换。"""
        """Save template to resolution subdirectory."""
        _ensure_resolution_dir(resolution)
        dest = TEMPLATE_DIR / resolution / filename
        if not _safe_resolve(dest, TEMPLATE_DIR / resolution):
            raise ValueError("Path traversal detected")
        dest.write_bytes(content)
        self._md5_cache.pop(f"{resolution}/{filename}", None)
        return dest


template_service = TemplateService()
