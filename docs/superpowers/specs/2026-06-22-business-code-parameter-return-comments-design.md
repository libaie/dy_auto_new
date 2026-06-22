# Business Code Parameter and Return Chinese Comments Design

## Context

The project now verifies Chinese module comments, high-risk side-effect comments, and Chinese comments for business classes/functions. The remaining requirement is stricter: class parameters, method/function inputs, and outputs also need Chinese comments.

This should extend the existing checker instead of creating a separate documentation system.

## Decision

Add a declaration-contract standard:

- Python classes must document `类参数`.
- Python functions and methods must document `入参` and `出参` or `返回`.
- JS/Vue/TS/device named functions and methods must have nearby Chinese comments for `入参` and `出参`.
- When parameter names can be parsed safely, generated comments should include those names.

Do not require comments for anonymous callbacks, inline lambdas, template event handlers, or generated/static code.

## Comment Shape

Python class:

```python
class RunCreate(BaseModel):
    """视频生产创建请求。

    类参数：series_id、episode_id、run_type 承载创建生产运行所需的业务字段。
    """
```

Python function/method:

```python
def start_episode_production(db: Session, series_id: str) -> dict:
    """启动剧集生产。

    入参：db、series_id 为该业务流程需要的上下文和标识。
    出参：返回生产运行创建或阻断结果。
    """
```

JS/Vue/TS/device:

```js
// 创建视频生产运行。
// 入参：seriesId、episodeId 为后端生产计划绑定参数。
// 出参：返回后端创建的生产运行。
export function createVideoProductionRun(seriesId, episodeId) {
  ...
}
```

## Verification

Extend `scripts/check_chinese_comments.py`:

1. Add contract gap detection in addition to module/risk/declaration checks.
2. Python:
   - use `ast` to read class/function docstrings;
   - class docstrings must include `类参数`;
   - function/method docstrings must include `入参` and either `出参` or `返回`;
   - if a declaration has parseable non-`self`/`cls` parameter names, the docstring must mention each name.
3. JS/Vue/TS/device:
   - reuse existing named declaration detection;
   - comment window must include `入参` and `出参` or `返回`;
   - if simple parameter names are parseable, the comment window must mention each name.
4. CLI output should include:

```text
CONTRACT path/to/file.py:12 function run missing 入参/出参
```

## Acceptance Criteria

- Existing module/risk/declaration checks still pass.
- Full strict checker reports zero contract gaps.
- Checker tests cover missing and passing Python/JS contract comments.
- Python code compiles.
- Frontend tests still pass.
- Device JavaScript files touched by the rollout pass `node --check`.

## Self-Review

- No placeholders remain.
- Scope preserves the full production business inventory.
- The design verifies the user's explicit class-parameter, input, and output requirement without forcing comments on anonymous callbacks.
