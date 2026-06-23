from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


_CJK = re.compile(r"[\u4e00-\u9fff]")


@dataclass(frozen=True)
class CheckResult:
    module_missing: list[Path]
    risk_missing: list[tuple[Path, int, str]]
    declaration_missing: list[tuple[Path, int, str, str]]
    contract_missing: list[tuple[Path, int, str, str, str]]


def _has_chinese(text: str | None) -> bool:
    return bool(text and _CJK.search(text))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def has_chinese_module_comment(path: Path) -> bool:
    text = _read(path).lstrip()
    if path.suffix == ".py":
        try:
            return _has_chinese(ast.get_docstring(ast.parse(text)))
        except SyntaxError:
            return False
    if path.suffix == ".vue":
        return text.startswith("<!--") and _has_chinese(text.split("-->", 1)[0])
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first.startswith("//") and _has_chinese(first)


def _py_declarations(path: Path):
    try:
        tree = ast.parse(_read(path))
    except SyntaxError:
        return []
    return [
        (node.lineno, "class" if isinstance(node, ast.ClassDef) else "function", node.name, ast.get_docstring(node), node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _js_declarations(path: Path):
    for lineno, line in enumerate(_read(path).splitlines(), start=1):
        match = re.search(r"(?:export\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", line)
        if match:
            yield lineno, "function", match.group(1), match.group(2)


def _previous_chinese(lines: list[str], lineno: int) -> bool:
    if lineno <= 1 or not _has_chinese(lines[lineno - 2]):
        return False
    return any(line.strip() for line in lines[: lineno - 2])


def _nearby_chinese(lines: list[str], lineno: int) -> bool:
    start = max(0, lineno - 3)
    return any(_has_chinese(line) for line in lines[start : lineno - 1])


def declaration_comment_gaps(path: Path) -> list[tuple[int, str, str]]:
    if path.suffix == ".py":
        return [(line, kind, name) for line, kind, name, doc, _node in _py_declarations(path) if not _has_chinese(doc)]
    if path.suffix in {".js", ".vue"}:
        lines = _read(path).splitlines()
        return [(line, kind, name) for line, kind, name, _params in _js_declarations(path) if not _previous_chinese(lines, line)]
    return []


def _param_names(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    names = [arg.arg for arg in args if arg.arg not in {"self", "cls"}]
    if node.args.vararg:
        names.append(node.args.vararg.arg)
    if node.args.kwarg:
        names.append(node.args.kwarg.arg)
    return names


def _contract_ok(doc: str | None, names: list[str], *, is_class: bool = False) -> bool:
    if is_class:
        return bool(doc and "类参数" in doc and all(name in doc for name in names))
    return bool(doc and "入参" in doc and "出参" in doc and all(name in doc for name in names))


def contract_comment_gaps(path: Path) -> list[tuple[int, str, str, str]]:
    if path.suffix == ".py":
        gaps = []
        for line, kind, name, doc, node in _py_declarations(path):
            if kind == "class":
                names = [n.target.id for n in getattr(node, "body", []) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]
                if names and not _contract_ok(doc, names, is_class=True):
                    gaps.append((line, kind, name, "missing 类参数/参数名"))
            elif not _contract_ok(doc, _param_names(node)):
                gaps.append((line, kind, name, "missing 入参/出参/参数名"))
        return gaps
    if path.suffix in {".js", ".vue"}:
        lines = _read(path).splitlines()
        gaps = []
        for line, kind, name, params in _js_declarations(path):
            names = [p.strip() for p in params.split(",") if p.strip()]
            nearby = "\n".join(lines[max(0, line - 4) : line - 1])
            if not ("入参" in nearby and "出参" in nearby and all(n in nearby for n in names)):
                gaps.append((line, kind, name, "missing 入参/出参/参数名"))
        return gaps
    return []


def high_risk_comment_gaps(path: Path) -> list[tuple[int, str]]:
    lines = _read(path).splitlines()
    gaps = []
    risk = ("provider.submit(", ".submit(", ".click(")
    for idx, line in enumerate(lines, start=1):
        if any(item in line for item in risk) and not line.lstrip().startswith(("def ", "async def ")):
            if not _nearby_chinese(lines, idx):
                gaps.append((idx, line.strip()))
    return gaps


def inventory(scope: str) -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    if scope != "all":
        return [Path(scope)]
    targets = [
        root / "app" / "domains" / "video_production",
        root / "app" / "domains" / "ai_video_series",
        root / "app" / "domains" / "ai_text_artifacts",
        root / "app" / "domains" / "storyboard_images",
        root / "app" / "domains" / "agency_operations",
        root / "app" / "domains" / "system_configuration",
        root / "app" / "domains" / "system_operations",
    ]
    paths: list[Path] = []
    for target in targets:
        if target.exists():
            paths.extend(p for p in target.rglob("*") if p.suffix in {".py", ".js", ".vue"})
    return paths


def check_files(paths: list[Path], *, strict_risk: bool = False) -> CheckResult:
    module_missing: list[Path] = []
    risk_missing: list[tuple[Path, int, str]] = []
    declaration_missing: list[tuple[Path, int, str, str]] = []
    contract_missing: list[tuple[Path, int, str, str, str]] = []
    for path in paths:
        if not has_chinese_module_comment(path):
            module_missing.append(path)
        if strict_risk:
            risk_missing.extend((path, line, text) for line, text in high_risk_comment_gaps(path))
        declaration_missing.extend((path, line, kind, name) for line, kind, name in declaration_comment_gaps(path))
        contract_missing.extend((path, line, kind, name, reason) for line, kind, name, reason in contract_comment_gaps(path))
    return CheckResult(module_missing, risk_missing, declaration_missing, contract_missing)
