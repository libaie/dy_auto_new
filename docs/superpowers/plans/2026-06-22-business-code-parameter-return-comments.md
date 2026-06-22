# Business Code Parameter and Return Chinese Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure included production business declarations document class parameters, function/method inputs, and outputs in Chinese.

**Architecture:** Extend the existing checker with contract-comment validation. Use Python `ast` for Python class/function docstrings and the existing conservative JS declaration scanner for JS/Vue/TS/device comments, then mechanically upgrade existing declaration comments.

**Tech Stack:** Python standard library, pytest, existing frontend vitest, Node syntax check.

---

## Scope Lock

Implement `docs/superpowers/specs/2026-06-22-business-code-parameter-return-comments-design.md`.

Keep the existing inventory and exclusions in `scripts/check_chinese_comments.py`.

## Files

- Modify `scripts/check_chinese_comments.py`
  - Add `contract_missing` to `CheckResult`.
  - Add Python and JS contract gap checks.
  - Extend CLI output with `CONTRACT` rows.
- Modify `server/tests/test_chinese_comment_checker.py`
  - Add failing tests for missing class parameter, input, and output comments.
  - Extend project-level regression to assert `contract_missing == []`.
- Modify included production files reported by the checker.
  - Upgrade Python class/function docstrings with `类参数`, `入参`, and `出参`.
  - Upgrade JS/Vue/TS/device comments with `入参` and `出参`.

## Task 1: Add Contract Checker Tests

**Files:**
- Modify: `server/tests/test_chinese_comment_checker.py`

- [ ] **Step 1: Write failing tests**

Add import:

```python
from scripts.check_chinese_comments import contract_comment_gaps
```

Add tests:

```python
def test_python_function_contract_requires_input_and_output_comments(tmp_path: Path):
    path = tmp_path / "service.py"
    path.write_text(
        '"""视频生产服务。"""\n\n'
        "def run(series_id: str) -> dict:\n"
        '    """启动生产运行。"""\n'
        "    return {'series_id': series_id}\n",
        encoding="utf-8",
    )

    assert contract_comment_gaps(path) == [
        (3, "function", "run", "missing 入参/出参/参数名")
    ]


def test_python_function_contract_accepts_parameter_and_return_comments(tmp_path: Path):
    path = tmp_path / "service.py"
    path.write_text(
        '"""视频生产服务。"""\n\n'
        "def run(series_id: str) -> dict:\n"
        '    """启动生产运行。\\n\\n'
        '    入参：series_id 为系列标识。\\n'
        '    出参：返回生产运行结果。\\n'
        '    """\n'
        "    return {'series_id': series_id}\n",
        encoding="utf-8",
    )

    assert contract_comment_gaps(path) == []


def test_python_class_contract_requires_class_parameters(tmp_path: Path):
    path = tmp_path / "models.py"
    path.write_text(
        '"""视频生产模型。"""\n\n'
        "class RunCreate:\n"
        '    """创建生产运行。"""\n'
        "    series_id: str\n",
        encoding="utf-8",
    )

    assert contract_comment_gaps(path) == [
        (3, "class", "RunCreate", "missing 类参数/参数名")
    ]


def test_javascript_function_contract_requires_input_and_output_comments(tmp_path: Path):
    path = tmp_path / "api.js"
    path.write_text(
        "// 前端 API 客户端。\n"
        "// 创建生产运行。\n"
        "export function createRun(seriesId) { return client.post('/runs', { seriesId }) }\n",
        encoding="utf-8",
    )

    assert contract_comment_gaps(path) == [
        (3, "function", "createRun", "missing 入参/出参/参数名")
    ]


def test_javascript_function_contract_accepts_input_and_output_comments(tmp_path: Path):
    path = tmp_path / "api.js"
    path.write_text(
        "// 前端 API 客户端。\n"
        "// 创建生产运行。\n"
        "// 入参：seriesId 为系列标识。\n"
        "// 出参：返回后端创建结果。\n"
        "export function createRun(seriesId) { return client.post('/runs', { seriesId }) }\n",
        encoding="utf-8",
    )

    assert contract_comment_gaps(path) == []
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\tests\test_chinese_comment_checker.py -q
```

Expected: fail because `contract_comment_gaps` is not implemented.

## Task 2: Implement Contract Checker

**Files:**
- Modify: `scripts/check_chinese_comments.py`
- Modify: `server/tests/test_chinese_comment_checker.py`

- [ ] **Step 1: Add result field**

Change `CheckResult`:

```python
@dataclass(frozen=True)
class CheckResult:
    module_missing: list[Path]
    risk_missing: list[tuple[Path, int, str]]
    declaration_missing: list[tuple[Path, int, str, str]]
    contract_missing: list[tuple[Path, int, str, str, str]]
```

- [ ] **Step 2: Add Python helpers**

Implement helpers:

```python
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
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            names.extend(_python_param_names(item))
    return sorted(set(name for name in names if not name.startswith("_")))
```

- [ ] **Step 3: Add contract detection**

Implement:

```python
def _has_input_output_contract(text: str, params: list[str]) -> bool:
    if "入参" not in text:
        return False
    if "出参" not in text and "返回" not in text:
        return False
    return all(name in text for name in params)
```

Python functions must pass `_has_input_output_contract`. Python classes must contain `类参数` and every parseable class parameter name.

JS functions use the comment window already used by declaration checks.

- [ ] **Step 4: Wire `check_files` and CLI**

Populate `contract_missing` when `strict_risk=True`.

CLI summary should print:

```text
checked=376 module_missing=0 risk_missing=0 declaration_missing=0 contract_missing=0
```

Each gap:

```text
CONTRACT path/to/file.py:12 function run missing 入参/出参/参数名
```

- [ ] **Step 5: Update existing tests**

Update `CheckResult(...)` equality assertions and project regression to include `contract_missing`.

- [ ] **Step 6: Run checker tests**

Run:

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\tests\test_chinese_comment_checker.py -q
```

Expected: pass except project-level contract assertion may be temporarily disabled until Task 3 fills gaps.

- [ ] **Step 7: Commit checker**

```powershell
git add scripts\check_chinese_comments.py server\tests\test_chinese_comment_checker.py
git commit -m "test: check parameter return chinese comments"
```

## Task 3: Upgrade Declaration Comments

**Files:**
- Modify: included files from `inventory("all")`

- [ ] **Step 1: Capture current gaps**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: fail with `CONTRACT` rows.

- [ ] **Step 2: Use a temporary script to upgrade Python docstrings**

Create a temporary script under `scripts/_tmp_add_contract_comments.py` that:

- imports `inventory`;
- parses Python files with `ast`;
- replaces class docstrings with one containing `类参数`;
- replaces function docstrings with one containing `入参` and `出参`;
- mentions parseable parameter names.

Do not commit the temporary script.

- [ ] **Step 3: Upgrade JS/Vue/TS/device comments**

The same temporary script should:

- find existing named declaration comment windows;
- insert `// 入参：...` and `// 出参：...` immediately above the declaration when missing;
- mention simple parameter names when parseable.

- [ ] **Step 4: Delete the temporary script**

Delete `scripts/_tmp_add_contract_comments.py` after the mechanical rewrite.

- [ ] **Step 5: Re-enable project-level contract assertion**

Ensure `test_all_business_code_has_standard_chinese_comments` asserts:

```python
assert result.contract_missing == []
```

- [ ] **Step 6: Run strict checker**

Run:

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: `checked=376 module_missing=0 risk_missing=0 declaration_missing=0 contract_missing=0`.

- [ ] **Step 7: Commit contract comments**

```powershell
git add server/app web/src device server/tests/test_chinese_comment_checker.py
git commit -m "docs: add chinese parameter return comments"
```

## Task 4: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run strict checker**

```powershell
.\server\.venv\Scripts\python.exe scripts\check_chinese_comments.py --scope all --strict-risk
```

Expected: `checked=376 module_missing=0 risk_missing=0 declaration_missing=0 contract_missing=0`.

- [ ] **Step 2: Run checker tests**

```powershell
.\server\.venv\Scripts\python.exe -m pytest server\tests\test_chinese_comment_checker.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Python compile check**

```powershell
.\server\.venv\Scripts\python.exe -m compileall -q server/app
```

Expected: exit code 0.

- [ ] **Step 4: Run frontend tests**

```powershell
D:\kaifa\nodejs24\npx.cmd vitest run
```

Expected: all frontend tests pass.

- [ ] **Step 5: Run touched device syntax checks**

```powershell
D:\kaifa\nodejs24\node.exe --check <each touched device js file>
```

Expected: exit code 0 for each file.

- [ ] **Step 6: Run whitespace check**

```powershell
git diff --check
```

Expected: no whitespace errors.

## Self-Review

- Spec coverage: checker and rollout cover class parameters, function inputs, and outputs.
- Verification coverage: strict checker and tests prove zero gaps.
- Scope control: anonymous callbacks remain excluded.
- No new dependency is introduced.
