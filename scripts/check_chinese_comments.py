from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
BUSINESS_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".vue"}
BATCH1_DIRS = [
    "server/app/domains/ai_video_series",
    "server/app/domains/agency_operations",
    "server/app/domains/video_production",
    "server/app/domains/image_generation",
    "server/app/domains/pixelle_integration",
    "server/app/domains/seedance_integration",
    "server/app/domains/model_configuration",
    "server/app/domains/quality_audit",
]
INCLUDE_GLOBS = [
    "server/app/domains/**/*.py",
    "server/app/main.py",
    "server/app/models/**/*.py",
    "server/app/utils/**/*.py",
    "web/src/**/*.vue",
    "web/src/**/*.js",
    "web/src/**/*.ts",
    "web/src/**/*.tsx",
    "device/main.js",
    "device/config.js",
    "device/core/**/*.js",
    "device/handlers/**/*.js",
    "device/utils/**/*.js",
]
EXCLUDED_PARTS = {
    "__pycache__",
    "__tests__",
    ".pytest_cache",
    "node_modules",
    "static",
    "template_images",
    "test",
    "tests",
    "spike",
}
BACKEND_HIGH_RISK_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\bprovider\.\w+\(",
        r"\bsubmit_[a-zA-Z0-9_]+\(",
        r"\bquery_[a-zA-Z0-9_]+\(",
        r"\benqueue_job\(",
        r"\breserve[a-zA-Z0-9_]*\(",
        r"\bhttpx\.(AsyncClient|get|post|stream)\(",
    )
]
DEVICE_HIGH_RISK_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"\b(click|swipe|setText|captureScreen|press)\(",
    )
]
DEVICE_RISK_EXCLUDED_FILES = {
    "device/core/floating-window.js",
}


@dataclass(frozen=True)
class CheckResult:
    module_missing: list[Path]
    risk_missing: list[tuple[Path, int, str]]


def _has_chinese(text: str) -> bool:
    return bool(CHINESE_RE.search(text))


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def inventory(scope: str = "all", root: Path = ROOT) -> list[Path]:
    if scope == "batch1":
        files: list[Path] = []
        for dirname in BATCH1_DIRS:
            files.extend((root / dirname).rglob("*.py"))
        return sorted(path for path in files if not _is_excluded(path))

    files = []
    for pattern in INCLUDE_GLOBS:
        files.extend(root.glob(pattern))
    return sorted(
        path
        for path in files
        if path.is_file() and path.suffix in BUSINESS_SUFFIXES and not _is_excluded(path)
    )


def _first_meaningful_lines(path: Path, limit: int = 40) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    result = []
    for line in lines[:limit]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#!") or stripped.startswith("# -*-"):
            continue
        result.append(stripped)
        if len(result) >= 8:
            break
    return result


def has_chinese_module_comment(path: Path) -> bool:
    lines = _first_meaningful_lines(path)
    if not lines:
        return False
    text = "\n".join(lines)
    if path.suffix == ".py":
        return text.startswith(('"""', "'''")) and _has_chinese(text)
    if path.suffix == ".vue":
        return text.startswith(("<!--", "//", "/*")) and _has_chinese(text)
    return text.startswith(("//", "/*")) and _has_chinese(text)


def high_risk_comment_gaps(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    path_key = path.as_posix()
    if any(path_key.endswith(item) for item in DEVICE_RISK_EXCLUDED_FILES):
        return []
    patterns = DEVICE_HIGH_RISK_PATTERNS if "/device/" in f"/{path_key}" else BACKEND_HIGH_RISK_PATTERNS
    gaps: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "async def ", "except ")):
            continue
        if not any(pattern.search(line) for pattern in patterns):
            continue
        window = "\n".join(lines[max(0, index - 5): index + 1])
        if _has_chinese(window):
            continue
        gaps.append((index + 1, line.strip()[:120]))
    return gaps


def check_files(paths: Iterable[Path], *, strict_risk: bool) -> CheckResult:
    module_missing = []
    risk_missing = []
    for path in paths:
        if not has_chinese_module_comment(path):
            module_missing.append(path)
        if strict_risk:
            for line_no, line in high_risk_comment_gaps(path):
                risk_missing.append((path, line_no, line))
    return CheckResult(module_missing=module_missing, risk_missing=risk_missing)


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check standard Chinese comments in business code.")
    parser.add_argument("--scope", choices=["all", "batch1"], default="all")
    parser.add_argument("--strict-risk", action="store_true")
    args = parser.parse_args()

    files = inventory(args.scope)
    result = check_files(files, strict_risk=args.strict_risk)
    print(
        f"checked={len(files)} "
        f"module_missing={len(result.module_missing)} "
        f"risk_missing={len(result.risk_missing)}"
    )
    for path in result.module_missing:
        print(f"MODULE {_relative(path)}")
    for path, line_no, line in result.risk_missing:
        print(f"RISK {_relative(path)}:{line_no} {line}")
    return 1 if result.module_missing or result.risk_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
