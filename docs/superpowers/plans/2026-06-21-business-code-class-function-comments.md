# Business Code Class and Function Chinese Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every included production business class and named function has a standard Chinese comment.

**Architecture:** Extend the existing comment checker with declaration coverage. Use Python `ast` for Python declarations and conservative line matching for JS/Vue/TS/device named declarations, then mechanically add concise Chinese docstrings/comments where the checker reports gaps.

**Tech Stack:** Python standard library, pytest, existing Node syntax check.

---

## Scope Lock

Implement the design in `docs/superpowers/specs/2026-06-21-business-code-class-function-comments-design.md`.

Keep the existing business inventory from `scripts/check_chinese_comments.py`. Do not scan tests, spike code, generated files, static assets, package files, docs, or caches.

## File Structure

- Modify `scripts/check_chinese_comments.py`
  - Add declaration gap detection.
  - Preserve existing module and high-risk checks.
- Modify `server/tests/test_chinese_comment_checker.py`
  - Add tests for Python class/function docstrings.
  - Add tests for JS named function comments.
  - Update project-level regression to assert declaration gaps are empty.
- Modify included production business files reported by the checker.
  - Add Python docstrings immediately inside classes/functions.
  - Add JS/Vue/TS/device Chinese comments immediately above named declarations.

## Task 1: Extend Checker Tests

**Files:**
- Modify: `server/tests/test_chinese_comment_checker.py`

- [ ] **Step 1: Add failing declaration tests**

Add imports and tests:

```python
from scripts.check_chinese_comments import declaration_comment_gaps


def test_python_declarations_require_chinese_docstrings(tmp_path: Path):
    path = tmp_path / "service.py"
    path.write_text(
        '"""视频生产服务。"""\n\n'
        "class Runner:\n"
        "    pass\n\n"
        "def run():\n"
        "    return True\n",
        encoding="utf-8",
    )

    assert declaration_comment_gaps(path) == [
        (3, "class", "Runner"),
        (6, "function", "run"),
    ]


def test_python_declarations_accept_chinese_docstrings(tmp_path: Path):
    path = tmp_path / "service.py"
    path.write_text(
        '"""视频生产服务。"""\n\n'
        "class Runner:\n"
        '    """生产任务运行器。"""\n'
        "    def run(self):\n"
        '        """执行一次生产任务。"""\n'
        "        return True\n",
        encoding="utf-8",
    )

    assert declaration_comment_gaps(path) == []


def test_javascript_named_function_requires_nearby_chinese_comment(tmp_path: Path):
    path = tmp_path / "api.js"
    path.write_text(
        "// 前端 API 客户端。\n"
        "export function createRun() { return client.post('/runs') }\n",
        encoding="utf-8",
    )

    assert declaration_comment_gaps(path) == [(2, "function", "createRun")]


def test_javascript_named_function_accepts_nearby_chinese_comment(tmp_path: Path):
    path = tmp_path / "api.js"
    path.write_text(
        "// 前端 API 客户端。\n"
        "// 创建生产运行。\n"
        "export function createRun() { return client.post('/runs') }\n",
        encoding="utf-8",
    )

    assert declaration_comment_gaps(path) == []
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\tests\test_chinese_comment_checker.py -q
```

Expected: fail because `declaration_comment_gaps` is not implemented.

## Task 2: Implement Declaration Checker

**Files:**
- Modify: `scripts/check_chinese_comments.py`
- Modify: `server/tests/test_chinese_comment_checker.py`

- [ ] **Step 1: Add declaration fields**

Change `CheckResult` to:

```python
@dataclass(frozen=True)
class CheckResult:
    module_missing: list[Path]
    risk_missing: list[tuple[Path, int, str]]
    declaration_missing: list[tuple[Path, int, str, str]]
```

- [ ] **Step 2: Add Python AST detection**

Implement:

```python
def _python_declaration_gaps(path: Path) -> list[tuple[int, str, str]]:
    import ast

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
```

- [ ] **Step 3: Add JS declaration detection**

Implement conservative patterns:

```python
JS_DECLARATION_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
    re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b"),
    re.compile(r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\("),
    re.compile(r"^\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+)\s*=\s*(?:async\s+)?function\s*\("),
    re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*:\s*(?:async\s+)?function\s*\("),
]
```

Use the previous five lines as the Chinese comment window.

- [ ] **Step 4: Wire CLI output**

Update `check_files()` to populate `declaration_missing`. Print each gap as:

```text
DECL path/to/file.py:12 function run_style_lock_job
```

Update the exit condition to fail when any of the three gap lists is non-empty.

- [ ] **Step 5: Update existing tests**

Update previous `CheckResult(...)` equality assertions to include `declaration_missing=[]`.

- [ ] **Step 6: Verify checker tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\tests\test_chinese_comment_checker.py -q
```

Expected: pass.

- [ ] **Step 7: Commit checker extension**

```powershell
git add scripts\check_chinese_comments.py server\tests\test_chinese_comment_checker.py
git commit -m "test: check business declaration chinese comments"
```

## Task 3: Add Declaration Comments

**Files:**
- Modify: included production files reported by `scripts/check_chinese_comments.py --scope all --strict-risk`

- [ ] **Step 1: Capture declaration gaps**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: fail with `DECL` rows.

- [ ] **Step 2: Add missing Python docstrings**

For every Python class/function gap, insert a one-line Chinese docstring as the first body statement:

```python
"""业务函数：说明该函数负责的业务流程、校验或数据转换。"""
```

Use the declaration name and file context to keep the sentence concise.

- [ ] **Step 3: Add missing JS/Vue/TS comments**

For every JS/Vue/TS/device named declaration gap, insert one Chinese comment above the declaration:

```js
// 业务函数：说明该函数协调的前端流程、接口调用或设备动作。
```

Use device-specific wording for device files and frontend-specific wording for `web/src`.

- [ ] **Step 4: Re-run strict checker**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: `checked=376 module_missing=0 risk_missing=0 declaration_missing=0`.

- [ ] **Step 5: Commit declaration comments**

```powershell
git add server/app web/src device scripts/check_chinese_comments.py server/tests/test_chinese_comment_checker.py
git commit -m "docs: add chinese comments to business declarations"
```

## Task 4: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run strict checker**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: `checked=376 module_missing=0 risk_missing=0 declaration_missing=0`.

- [ ] **Step 2: Run checker regression tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\tests\test_chinese_comment_checker.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Python compile check**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m compileall -q server/app
```

Expected: exit code 0.

- [ ] **Step 4: Run touched device syntax checks**

Run:

```powershell
D:\kaifa\nodejs24\node.exe --check device/main.js
```

Expected: exit code 0. Repeat for any touched device `.js` file.

- [ ] **Step 5: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

## Self-Review

- Spec coverage: Tasks 1-3 cover Python classes/functions and JS/Vue/TS/device named declarations.
- Verification coverage: Task 4 proves module, risk, and declaration coverage together.
- Scope control: anonymous callbacks and inline arrow functions remain excluded as designed.
- No new dependency is introduced.
