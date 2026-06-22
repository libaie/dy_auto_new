from __future__ import annotations

import argparse
import ast
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
JS_DECLARATION_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
        r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b",
        r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\(",
        r"^\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\s*=\s*(?:async\s+)?function\s*\(",
        r"^\s*([A-Za-z_$][\w$]*)\s*:\s*(?:async\s+)?function\s*\(",
    )
]
JS_DECLARATION_WITH_PARAMS_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)",
        r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\(([^)]*)\)",
        r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>",
        r"^\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\s*=\s*(?:async\s+)?function\s*\(([^)]*)\)",
        r"^\s*([A-Za-z_$][\w$]*)\s*:\s*(?:async\s+)?function\s*\(([^)]*)\)",
        r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*\{",
    )
]
JS_CONTROL_KEYWORDS = {
    "catch",
    "for",
    "if",
    "switch",
    "while",
    "with",
}


@dataclass(frozen=True)
class CheckResult:
    module_missing: list[Path]
    risk_missing: list[tuple[Path, int, str]]
    declaration_missing: list[tuple[Path, int, str, str]]
    contract_missing: list[tuple[Path, int, str, str, str]]


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


def _python_declaration_gaps(path: Path) -> list[tuple[int, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    gaps = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not _has_chinese(ast.get_docstring(node) or ""):
                gaps.append((node.lineno, "class", node.name))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _has_chinese(ast.get_docstring(node) or ""):
                gaps.append((node.lineno, "function", node.name))
    return sorted(gaps)


def _js_comment_window_has_chinese(lines: list[str], declaration_index: int) -> bool:
    start = max(0, declaration_index - 5)
    window = lines[start:declaration_index]
    if declaration_index <= 2 and len([line for line in window if line.strip()]) <= 1:
        return False
    return _has_chinese("\n".join(window))


def _js_declaration_gaps(path: Path) -> list[tuple[int, str, str]]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    gaps: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        for pattern in JS_DECLARATION_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            if not _js_comment_window_has_chinese(lines, index):
                gaps.append((index + 1, "function", match.group(1)))
            break
    return gaps


def _python_param_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = [
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    names = [arg.arg for arg in args if arg.arg not in {"self", "cls"}]
    if node.args.vararg and node.args.vararg.arg not in {"self", "cls"}:
        names.append(node.args.vararg.arg)
    if node.args.kwarg and node.args.kwarg.arg not in {"self", "cls"}:
        names.append(node.args.kwarg.arg)
    return names


def _python_class_param_names(node: ast.ClassDef) -> list[str]:
    names = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            names.append(item.target.id)
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            names.extend(_python_param_names(item))
    return sorted(set(name for name in names if not name.startswith("_")))


def _has_input_output_contract(text: str, params: list[str]) -> bool:
    if "入参" not in text:
        return False
    if "出参" not in text and "返回" not in text:
        return False
    return all(name in text for name in params)


def _python_contract_gaps(path: Path) -> list[tuple[int, str, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    gaps: list[tuple[int, str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            params = _python_class_param_names(node)
            if "类参数" not in doc or not all(name in doc for name in params):
                gaps.append((node.lineno, "class", node.name, "missing 类参数/参数名"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            if not _has_input_output_contract(doc, _python_param_names(node)):
                gaps.append((node.lineno, "function", node.name, "missing 入参/出参/参数名"))
    return sorted(gaps)


def _simple_js_param_names(raw: str) -> list[str]:
    names = []
    for item in raw.split(","):
        item = item.strip()
        if not item or any(char in item for char in "{}[]"):
            continue
        item = item.split("=", 1)[0].strip()
        item = item.lstrip(".").strip()
        if re.match(r"^[A-Za-z_$][\w$]*$", item):
            names.append(item)
    return names


def _js_declaration_with_params(line: str) -> tuple[str, list[str]] | None:
    for pattern in JS_DECLARATION_WITH_PARAMS_PATTERNS:
        match = pattern.search(line)
        if match:
            name = match.group(1)
            if name in JS_CONTROL_KEYWORDS:
                return None
            return name, _simple_js_param_names(match.group(2))
    return None


def _js_contract_gaps(path: Path) -> list[tuple[int, str, str, str]]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    gaps: list[tuple[int, str, str, str]] = []
    for index, line in enumerate(lines):
        parsed = _js_declaration_with_params(line)
        if not parsed:
            continue
        name, params = parsed
        text = "\n".join(lines[max(0, index - 5):index])
        if not _has_input_output_contract(text, params):
            gaps.append((index + 1, "function", name, "missing 入参/出参/参数名"))
    return gaps


def contract_comment_gaps(path: Path) -> list[tuple[int, str, str, str]]:
    if path.suffix == ".py":
        return _python_contract_gaps(path)
    if path.suffix in {".js", ".ts", ".tsx", ".vue"}:
        return _js_contract_gaps(path)
    return []


def declaration_comment_gaps(path: Path) -> list[tuple[int, str, str]]:
    if path.suffix == ".py":
        return _python_declaration_gaps(path)
    if path.suffix in {".js", ".ts", ".tsx", ".vue"}:
        return _js_declaration_gaps(path)
    return []


def check_files(paths: Iterable[Path], *, strict_risk: bool) -> CheckResult:
    module_missing = []
    risk_missing = []
    declaration_missing = []
    contract_missing = []
    for path in paths:
        if not has_chinese_module_comment(path):
            module_missing.append(path)
        if strict_risk:
            for line_no, line in high_risk_comment_gaps(path):
                risk_missing.append((path, line_no, line))
            for line_no, kind, name in declaration_comment_gaps(path):
                declaration_missing.append((path, line_no, kind, name))
            for line_no, kind, name, reason in contract_comment_gaps(path):
                contract_missing.append((path, line_no, kind, name, reason))
    return CheckResult(
        module_missing=module_missing,
        risk_missing=risk_missing,
        declaration_missing=declaration_missing,
        contract_missing=contract_missing,
    )


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
        f"risk_missing={len(result.risk_missing)} "
        f"declaration_missing={len(result.declaration_missing)} "
        f"contract_missing={len(result.contract_missing)}"
    )
    for path in result.module_missing:
        print(f"MODULE {_relative(path)}")
    for path, line_no, line in result.risk_missing:
        print(f"RISK {_relative(path)}:{line_no} {line}")
    for path, line_no, kind, name in result.declaration_missing:
        print(f"DECL {_relative(path)}:{line_no} {kind} {name}")
    for path, line_no, kind, name, reason in result.contract_missing:
        print(f"CONTRACT {_relative(path)}:{line_no} {kind} {name} {reason}")
    return (
        1
        if result.module_missing
        or result.risk_missing
        or result.declaration_missing
        or result.contract_missing
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
