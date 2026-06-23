from __future__ import annotations

import argparse
import ast
import fnmatch
import re
from pathlib import Path


SOURCE_ROOTS = (
    "server/app/domains/video_production",
    "server/app/domains/ai_video_series",
    "server/app/domains/ai_text_artifacts",
    "server/app/domains/storyboard_images",
    "server/app/domains/agency_operations",
    "server/app/domains/system_configuration",
    "server/app/domains/system_operations",
    "server/app/domains/model_configuration",
    "server/app/domains/pixelle_integration",
    "server/app/domains/script_pipeline",
)

EXTRA_FILES = (
    "server/app/main.py",
    "server/app/db/models/video_production.py",
    "server/app/db/models/ai_video_series.py",
    "server/app/db/models/ai_text_artifacts.py",
    "server/app/db/models/agency_operations.py",
    "server/app/db/models/model_configuration.py",
    "server/app/db/models/system_configuration.py",
    "server/app/db/models/script_pipeline.py",
    "server/app/db/models/production_observability.py",
    "server/scripts/smoke_bailian_one_sentence_e2e.py",
    "server/scripts/check_chinese_comments.py",
    "server/scripts/check_ai_video_report_coverage.py",
)

FRONTEND_FILES = (
    "web/src/router/index.js",
    "web/src/views/AITextArtifactWorkbenchPage.vue",
    "web/src/views/SeriesDetailPage.vue",
    "web/src/views/VideoProductionMonitorPage.vue",
    "web/src/views/AIVideoReviewPage.vue",
    "web/src/views/OneSentenceVideoPage.vue",
    "web/src/views/AgencyConsolePage.vue",
    "web/src/views/AIConfigPage.vue",
    "web/src/views/SeriesListPage.vue",
    "web/src/api/videoProduction.js",
    "web/src/api/storyboardImages.js",
    "web/src/api/agency.js",
    "web/src/api/series.js",
    "web/src/api/aiTextArtifacts.js",
    "web/src/api/aiConfig.js",
    "web/src/api/settings.js",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for source_root in SOURCE_ROOTS:
        base = root / source_root
        if base.exists():
            paths.extend(path for path in base.rglob("*.py") if path.name != "__init__.py")
    for extra in EXTRA_FILES:
        path = root / extra
        if path.exists() and path not in paths:
            paths.append(path)
    return sorted(paths)


def _frontend_files(root: Path) -> list[Path]:
    return [path for item in FRONTEND_FILES if (path := root / item).exists()]


def _declarations(path: Path) -> list[tuple[int, str]]:
    if path.suffix in {".js", ".vue"}:
        return _js_declarations(path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sorted(
        (node.lineno, node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )


def _js_declarations(path: Path) -> list[tuple[int, str]]:
    declarations: list[tuple[int, str]] = []
    patterns = (
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
        re.compile(r"^\s*(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"),
        re.compile(r"^\s*(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*computed\s*\("),
    )
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for pattern in patterns:
            if match := pattern.search(line):
                declarations.append((line_number, match.group(1)))
                break
    return declarations


def _reviewable_line_numbers(path: Path) -> list[int]:
    if path.suffix == ".py":
        tree = ast.parse(path.read_text(encoding="utf-8"))
        ranges: list[tuple[int, int]] = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                continue
            end = getattr(node, "end_lineno", node.lineno)
            ranges.append((node.lineno, end))
        return [
            line_number
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
            if line.strip() and any(start <= line_number <= end for start, end in ranges)
        ]
    lines: list[int] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "<!--")):
            continue
        if path.suffix != ".py" and stripped.startswith("*"):
            continue
        lines.append(line_number)
    return lines


def _matching_rels(files: list[Path], root: Path, name: str) -> list[str]:
    name = name.replace("\\", "/")
    if "*" in name:
        return [
            rel
            for path in files
            if fnmatch.fnmatch(rel := path.relative_to(root).as_posix(), name)
            or fnmatch.fnmatch(path.name, name)
        ]
    return [
        rel
        for path in files
        if (rel := path.relative_to(root).as_posix()) == name
        or rel.endswith("/" + name)
        or path.name == Path(name).name
    ]


def _report_whole_file_refs(report: str, files: list[Path], root: Path) -> set[str]:
    refs: set[str] = set()
    for line in report.splitlines():
        if not line.startswith("|"):
            continue
        first_cell = line.strip().strip("|").split("|", 1)[0].strip()
        for match in re.finditer(r"`([^`]+\.(?:py|js|vue))`", first_cell):
            if re.match(r":\d", first_cell[match.end() :]):
                continue
            refs.update(_matching_rels(files, root, match.group(1)))
    return refs


def _report_ranges(report: str, files: list[Path], root: Path) -> dict[str, list[tuple[int, int]]]:
    ranges = {path.relative_to(root).as_posix(): [] for path in files}
    current: str | None = None
    marker = "\u6587\u4ef6\uff1a`"
    for line in report.splitlines():
        if marker in line:
            after = line.split(marker, 1)[1]
            current = after.split("`", 1)[0].replace("\\", "/") if "`" in after else None
            continue
        if current and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            match = re.match(r"^(\d+)(?:-(\d+)|\+)?$", cells[0] if cells else "")
            if match:
                _add_range(ranges, files, root, current, int(match.group(1)), int(match.group(2) or "1000000"))
    for match in re.finditer(r"`([^`]+\.(?:py|js|vue))`:(\d+)(?:-(\d+)|\+)?", report):
        _add_range(ranges, files, root, match.group(1), int(match.group(2)), int(match.group(3) or "1000000"))
    return ranges


def _add_range(
    ranges: dict[str, list[tuple[int, int]]],
    files: list[Path],
    root: Path,
    name: str,
    start: int,
    end: int,
) -> None:
    for rel in _matching_rels(files, root, name):
        ranges[rel].append((start, end))


def _report_file_refs(report: str) -> list[str]:
    refs: set[str] = set()
    for code in re.findall(r"`([^`]+)`", report):
        for token in re.split(r"[\s,]+", code):
            token = token.strip(" .;:()[]，。；：）")
            if "::" in token:
                token = token.split("::", 1)[0]
            token = token.replace("\\", "/")
            if Path(token).suffix in {".py", ".js", ".vue", ".md"}:
                refs.add(token)
    return sorted(refs)


def _known_repo_files(root: Path) -> list[str]:
    files: list[str] = []
    for dirname in ("server/app", "server/scripts", "server/tests", "web/src", "docs"):
        base = root / dirname
        if base.exists():
            files.extend(path.relative_to(root).as_posix() for path in base.rglob("*") if path.is_file())
    return files


def _ref_exists(ref: str, known_files: list[str]) -> bool:
    candidates = [ref]
    if ref.startswith("tests/"):
        candidates.append("server/" + ref)
    if ref.startswith("src/"):
        candidates.append("web/" + ref)
    known_set = set(known_files)
    known_names = {Path(path).name for path in known_files}
    for candidate in candidates:
        if "*" in candidate:
            if any(fnmatch.fnmatch(path, candidate) for path in known_files):
                return True
            if "/" not in candidate and any(fnmatch.fnmatch(Path(path).name, candidate) for path in known_files):
                return True
        elif candidate in known_set:
            return True
    name = Path(ref).name
    return bool(name and name in known_names)


def _pytest_refs(report: str) -> list[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()
    for code in re.findall(r"`([^`]+)`", report):
        for token in re.split(r"[\s,]+", code):
            token = token.strip(" .;:()[]，。；：）")
            if "::" not in token:
                continue
            file_ref, node = token.split("::", 1)
            file_ref = file_ref.replace("\\", "/")
            node = node.strip(" .;:()[]，。；：）")
            if file_ref.endswith(".py") and node:
                refs.add((file_ref, node))
    return sorted(refs)


def _resolve_file_ref(ref: str, root: Path, known_files: list[str]) -> Path | None:
    candidates = [ref]
    if ref.startswith("tests/"):
        candidates.append("server/" + ref)
    if ref.startswith("src/"):
        candidates.append("web/" + ref)
    known_set = set(known_files)
    for candidate in candidates:
        if candidate in known_set:
            return root / candidate
    matches = [path for path in known_files if Path(path).name == Path(ref).name]
    return root / matches[0] if len(matches) == 1 else None


def _pytest_ref_exists(root: Path, known_files: list[str], file_ref: str, node_ref: str) -> bool:
    path = _resolve_file_ref(file_ref, root, known_files)
    if path is None or not path.exists():
        return False
    names = {name for _line, name in _declarations(path)}
    if "*" in node_ref:
        return any(fnmatch.fnmatch(name, node_ref) for name in names)
    return node_ref in names


def _source_line_coverage(
    files: list[Path],
    ranges: dict[str, list[tuple[int, int]]],
    whole_files: set[str],
    root: Path,
) -> tuple[int, int, list[str]]:
    total = covered = 0
    missing: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        for line in _reviewable_line_numbers(path):
            total += 1
            if rel in whole_files or any(start <= line <= end for start, end in ranges[rel]):
                covered += 1
            else:
                missing.append(f"{rel}:{line}")
    return total, covered, missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        default="docs/superpowers/reports/2026-06-22-ai-video-generation-code-review-audit.md",
    )
    args = parser.parse_args()
    root = _repo_root()
    report = (root / args.report).read_text(encoding="utf-8")
    files = [*_source_files(root), *_frontend_files(root)]
    ranges = _report_ranges(report, files, root)
    whole_files = _report_whole_file_refs(report, files, root)
    python_total = python_covered = frontend_total = frontend_covered = 0
    missing: list[str] = []
    source_total, source_covered, missing_source_lines = _source_line_coverage(files, ranges, whole_files, root)
    for path in files:
        rel = path.relative_to(root).as_posix()
        whole_file = rel in whole_files
        for line, name in _declarations(path):
            in_range = any(start <= line <= end for start, end in ranges[rel])
            if in_range or f"`{name}`" in report or name in report or (whole_file and not ranges[rel]):
                if path.suffix == ".py":
                    python_covered += 1
                else:
                    frontend_covered += 1
            else:
                missing.append(f"{rel}:{line} {name}")
            if path.suffix == ".py":
                python_total += 1
            else:
                frontend_total += 1
    file_refs = _report_file_refs(report)
    known_files = _known_repo_files(root)
    missing_file_refs = [ref for ref in file_refs if not _ref_exists(ref, known_files)]
    pytest_refs = _pytest_refs(report)
    missing_pytest_refs = [
        f"{file_ref}::{node_ref}"
        for file_ref, node_ref in pytest_refs
        if not _pytest_ref_exists(root, known_files, file_ref, node_ref)
    ]
    python_files = sum(1 for path in files if path.suffix == ".py")
    frontend_files = len(files) - python_files
    print(
        f"python_files={python_files} python_declarations={python_total} python_covered={python_covered} "
        f"frontend_files={frontend_files} frontend_declarations={frontend_total} frontend_covered={frontend_covered} "
        f"source_lines={source_total} source_lines_covered={source_covered} "
        f"missing_source_lines={len(missing_source_lines)} missing={len(missing)} "
        f"file_refs={len(file_refs)} missing_file_refs={len(missing_file_refs)} "
        f"pytest_refs={len(pytest_refs)} missing_pytest_refs={len(missing_pytest_refs)}"
    )
    for item in missing_source_lines[:50]:
        print(f"missing_source_line: {item}")
    for item in missing[:50]:
        print(item)
    for item in missing_file_refs[:50]:
        print(f"missing_file_ref: {item}")
    for item in missing_pytest_refs[:50]:
        print(f"missing_pytest_ref: {item}")
    return 1 if missing_source_lines or missing or missing_file_refs or missing_pytest_refs else 0


if __name__ == "__main__":
    raise SystemExit(main())
