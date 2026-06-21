# Business Code Chinese Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add standard Chinese comments to all production business code and make coverage verifiable.

**Architecture:** Add one lightweight checker that defines the business-code inventory and reports missing Chinese module comments plus high-risk side-effect comment gaps. Then annotate included production code in four batches: high-risk backend domains, remaining backend business domains, frontend workflows, and device automation scripts.

**Tech Stack:** Python standard library, pytest, existing backend/frontend/device test commands.

---

## Scope Lock

Implement against the design in `docs/superpowers/specs/2026-06-21-business-code-chinese-comments-design.md`.

Included code:

- `server/app/domains/**/*.py`
- `server/app/main.py`
- `server/app/models/**/*.py`
- `server/app/utils/**/*.py` when business behavior is present
- `web/src/**/*.vue`
- `web/src/**/*.js`
- `web/src/**/*.ts`
- `web/src/**/*.tsx`
- `device/main.js`
- `device/config.js`
- `device/core/**/*.js`
- `device/handlers/**/*.js`
- `device/utils/**/*.js`

Excluded code:

- `server/tests`, `web/src/__tests__`, `tests`, `device/test`
- `device/spike`
- package, lock, build, generated, archive, static asset, cache, docs, and report files

## File Structure

- Create `scripts/check_chinese_comments.py`
  - Owns business-code inventory, module-header checks, high-risk side-effect checks, and CLI output.
- Create `server/tests/test_chinese_comment_checker.py`
  - Unit tests for the checker using temporary files.
- Modify production business files reported by the checker.
  - Batch 1: high-risk backend domains.
  - Batch 2: remaining backend domains and business utilities.
  - Batch 3: frontend production workflows.
  - Batch 4: device production automation scripts.

## Comment Rules

Use Simplified Chinese only where it explains business meaning:

- module-level ownership;
- public route/service/job/worker/orchestration entry point purpose;
- provider calls, paid execution, queue workers, retries, idempotency, approval gates, budget gates, and device side effects;
- frontend workflow coordination.

Do not add syntax comments such as "遍历列表" or duplicate a function name in prose.

---

### Task 1: Add the Chinese Comment Coverage Checker

**Files:**
- Create: `scripts/check_chinese_comments.py`
- Create: `server/tests/test_chinese_comment_checker.py`

- [ ] **Step 1: Write failing checker tests**

Create `server/tests/test_chinese_comment_checker.py`:

```python
from pathlib import Path

from scripts.check_chinese_comments import (
    CheckResult,
    check_files,
    has_chinese_module_comment,
    high_risk_comment_gaps,
)


def test_python_file_requires_chinese_module_docstring(tmp_path: Path):
    good = tmp_path / "good.py"
    good.write_text('"""视频生产服务。"""\n\nVALUE = 1\n', encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text('"""Video production service."""\n\nVALUE = 1\n', encoding="utf-8")

    assert has_chinese_module_comment(good)
    assert not has_chinese_module_comment(bad)


def test_javascript_file_accepts_leading_chinese_comment(tmp_path: Path):
    good = tmp_path / "good.js"
    good.write_text("// 设备任务执行入口。\nexport const value = 1\n", encoding="utf-8")
    bad = tmp_path / "bad.js"
    bad.write_text("// task runner\nexport const value = 1\n", encoding="utf-8")

    assert has_chinese_module_comment(good)
    assert not has_chinese_module_comment(bad)


def test_vue_file_accepts_leading_chinese_html_comment(tmp_path: Path):
    good = tmp_path / "Good.vue"
    good.write_text("<!-- 生产控制台页面。 -->\n<template></template>\n", encoding="utf-8")

    assert has_chinese_module_comment(good)


def test_high_risk_line_requires_nearby_chinese_comment(tmp_path: Path):
    bad = tmp_path / "risk.py"
    bad.write_text('def run():\n    provider.submit()\n', encoding="utf-8")
    good = tmp_path / "ok.py"
    good.write_text('def run():\n    # 提交 provider 前已完成预算和幂等校验。\n    provider.submit()\n', encoding="utf-8")

    assert high_risk_comment_gaps(bad)
    assert high_risk_comment_gaps(good) == []


def test_check_files_reports_missing_module_comment(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text("VALUE = 1\n", encoding="utf-8")

    result = check_files([bad], strict_risk=False)

    assert result == CheckResult(module_missing=[bad], risk_missing=[])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chinese_comment_checker.py -q
```

Expected: FAIL because `scripts/check_chinese_comments.py` does not exist.

- [ ] **Step 3: Create the checker**

Create `scripts/check_chinese_comments.py`:

```python
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
HIGH_RISK_NEEDLES = [
    "provider",
    "submit",
    "query",
    "budget",
    "idempot",
    "queue",
    "worker",
    "retry",
    "approve",
    "reject",
    "httpx",
    "fetch(",
    "axios",
    "device",
    "click",
    "swipe",
]


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
    gaps: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        if not any(needle in lowered for needle in HIGH_RISK_NEEDLES):
            continue
        window = "\n".join(lines[max(0, index - 3): index + 1])
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
    print(f"checked={len(files)} module_missing={len(result.module_missing)} risk_missing={len(result.risk_missing)}")
    for path in result.module_missing:
        print(f"MODULE {_relative(path)}")
    for path, line_no, line in result.risk_missing:
        print(f"RISK {_relative(path)}:{line_no} {line}")
    return 1 if result.module_missing or result.risk_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run checker tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chinese_comment_checker.py -q
```

Expected: PASS.

- [ ] **Step 5: Run initial inventory report**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope batch1
```

Expected: non-zero exit with a list of Batch 1 files missing Chinese module comments. Keep this output as the working list for Task 2.

- [ ] **Step 6: Commit checker**

```powershell
git add scripts/check_chinese_comments.py server/tests/test_chinese_comment_checker.py
git commit -m "test: add business code chinese comment checker"
```

---

### Task 2: Annotate Batch 1 Backend High-Risk Domains

**Files:**
- Modify files reported by `scripts/check_chinese_comments.py --scope batch1`
- High-risk directories:
  - `server/app/domains/ai_video_series`
  - `server/app/domains/agency_operations`
  - `server/app/domains/video_production`
  - `server/app/domains/image_generation`
  - `server/app/domains/pixelle_integration`
  - `server/app/domains/seedance_integration`
  - `server/app/domains/model_configuration`
  - `server/app/domains/quality_audit`

- [ ] **Step 1: Capture current Batch 1 gaps**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope batch1
```

Expected: FAIL with file paths under the high-risk backend directories.

- [ ] **Step 2: Add module-level Chinese comments**

For each reported Python file, add a top-level module docstring before imports. Use this shape:

```python
"""业务域名称。

说明这个文件负责的业务流程、持久化对象或外部系统边界。
"""
```

Examples:

```python
"""AI 视频系列风格锁定服务。

负责生成和校验角色、场景、视觉风格与参考图，使后续分镜和生产阶段保持一致。
"""
```

```python
"""视频生产 provider 阶段执行器。

负责把本地生产作业转换为图片、视频或合成 provider 调用，并把外部任务状态同步回本地作业。
"""
```

- [ ] **Step 3: Add nearby comments for irreversible side effects**

Near provider calls, budget gates, idempotency checks, queue workers, approval gates, retry loops, and asset writes, add one-line Chinese comments. Use this shape:

```python
# 生产作业必须先完成预算和幂等校验，再提交付费 provider。
```

```python
# 这里只同步外部任务状态，本地资产落库由统一的生产作业结果处理。
```

- [ ] **Step 4: Run Batch 1 module coverage**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope batch1
```

Expected: PASS with `module_missing=0`.

- [ ] **Step 5: Run Batch 1 advisory risk coverage**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope batch1 --strict-risk
```

Expected: If it fails, inspect each `RISK` line and either add a useful Chinese business comment or tune `HIGH_RISK_NEEDLES` only when the match is clearly not business risk.

- [ ] **Step 6: Run related tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_project_langchain_ai_inventory.py server/tests/test_ai_video_langchain_inventory.py server/tests/test_ai_generator.py server/tests/test_audit_router_payload.py server/tests/test_video_studio_backend_closure.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Batch 1 comments**

```powershell
git add server/app/domains scripts/check_chinese_comments.py
git commit -m "docs: add chinese comments to high-risk backend flows"
```

---

### Task 3: Annotate Remaining Backend Business Code

**Files:**
- Modify remaining included backend production files from:
  - `server/app/domains/**/*.py`
  - `server/app/main.py`
  - `server/app/models/**/*.py`
  - `server/app/utils/**/*.py` when the file contains business behavior

- [ ] **Step 1: Capture remaining backend gaps**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all
```

Expected: FAIL while frontend and device files remain incomplete. Filter backend paths from the output.

- [ ] **Step 2: Add module comments to remaining backend files**

Add concise module docstrings. Use this shape:

```python
"""业务模块名称。

说明这个文件维护的业务对象、API 边界或运行时职责。
"""
```

- [ ] **Step 3: Add comments for backend side effects**

Add nearby Chinese comments for database writes, external service calls, audit records, background workers, and permission gates.

Use one-line comments unless a docstring is clearer:

```python
# 管理端操作必须经过角色校验，避免设备或普通账号触发业务配置变更。
```

- [ ] **Step 4: Run backend-related tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_model_configuration_auth_parity.py server/tests/test_device_operations_auth_parity.py server/tests/test_content_collection_auth_parity.py server/tests/test_system_operations_auth_parity.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit backend comments**

```powershell
git add server/app scripts/check_chinese_comments.py
git commit -m "docs: add chinese comments to backend business code"
```

---

### Task 4: Annotate Frontend Business Workflows

**Files:**
- Modify included frontend production files from:
  - `web/src/**/*.vue`
  - `web/src/**/*.js`
  - `web/src/**/*.ts`
  - `web/src/**/*.tsx`
- Exclude:
  - `web/src/__tests__`
  - pure CSS files
  - pure static assets

- [ ] **Step 1: Capture frontend gaps**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all
```

Expected: FAIL while frontend files still miss module comments. Filter `web/src` paths from the output.

- [ ] **Step 2: Add module comments to Vue pages and business modules**

For Vue files, place the comment before `<template>`:

```vue
<!-- 生产控制台页面：聚合 run、job、asset 三层状态，展示后端已归一化的生产进度。 -->
<template>
```

For JS/TS files, place the comment at the top:

```js
// AI 视频 API 客户端：封装系列、分镜、生产和审查相关的后端调用。
```

- [ ] **Step 3: Add workflow comments near complex UI orchestration**

Use one-line Chinese comments near polling, WebSocket reconciliation, approval actions, repair actions, and optimistic UI state:

```js
// 前端只负责触发返修动作，返修状态以后台任务和审查结果为准。
```

- [ ] **Step 4: Run frontend tests**

Run:

```powershell
D:\kaifa\nodejs24\npx.cmd vitest run
```

Expected: PASS.

- [ ] **Step 5: Commit frontend comments**

```powershell
git add web/src scripts/check_chinese_comments.py
git commit -m "docs: add chinese comments to frontend business workflows"
```

---

### Task 5: Annotate Device Automation Business Scripts

**Files:**
- Modify:
  - `device/main.js`
  - `device/config.js`
  - `device/core/**/*.js`
  - `device/handlers/**/*.js`
  - `device/utils/**/*.js`
- Exclude:
  - `device/test`
  - `device/spike`

- [ ] **Step 1: Capture device gaps**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all
```

Expected: FAIL while device files still miss module comments. Filter `device` production paths from the output.

- [ ] **Step 2: Add module comments to device files**

Use this top-of-file shape:

```js
// 抖音评论采集处理器：负责搜索结果进入、评论读取、用户主页采集和本地去重。
```

- [ ] **Step 3: Add comments near risky device actions**

Add comments near click, swipe, input, screenshot, OCR, pairing, WebSocket command handling, and anti-detect behavior:

```js
// 真实点击前再次确认节点仍在屏幕内，避免误触抖音的不可逆操作。
```

- [ ] **Step 4: Run device tests**

Run the existing Node tests that do not require a physical Android device:

```powershell
D:\kaifa\nodejs24\npx.cmd vitest run
```

Expected: PASS for repository frontend tests. If device-specific tests use a separate runner, run the existing documented command from `device` and record the exact output in the commit message body.

- [ ] **Step 5: Commit device comments**

```powershell
git add device scripts/check_chinese_comments.py
git commit -m "docs: add chinese comments to device automation code"
```

---

### Task 6: Enforce Full Coverage

**Files:**
- Modify: `scripts/check_chinese_comments.py`
- Modify or create one test file if needed: `server/tests/test_chinese_comment_checker.py`

- [ ] **Step 1: Run full checker**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: PASS with `module_missing=0` and `risk_missing=0`.

- [ ] **Step 2: Add project-level regression test**

If no project-level test already calls full scope, add this test to `server/tests/test_chinese_comment_checker.py`:

```python
from scripts.check_chinese_comments import check_files, inventory


def test_all_business_code_has_standard_chinese_comments():
    result = check_files(inventory("all"), strict_risk=True)

    assert result.module_missing == []
    assert result.risk_missing == []
```

- [ ] **Step 3: Run full regression**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server/tests/test_chinese_comment_checker.py -q
```

Expected: PASS.

- [ ] **Step 4: Run format/diff safety check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Commit enforcement**

```powershell
git add scripts/check_chinese_comments.py server/tests/test_chinese_comment_checker.py
git commit -m "test: enforce business code chinese comments"
```

---

## Self-Review

- Spec coverage: all included backend, frontend, and device business code is covered by Tasks 2 through 5.
- Verification coverage: Task 1 creates the checker; Task 6 turns full coverage into a regression test.
- Risk coverage: provider calls, paid execution, queues, retries, idempotency, approval gates, and device side effects are covered by high-risk scanning and manual comments.
- Scope control: tests, spike code, generated files, static assets, package files, and docs are excluded.
- No implementation step requires a new dependency.
