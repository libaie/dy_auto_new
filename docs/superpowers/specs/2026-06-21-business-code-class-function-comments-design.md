# Business Code Class and Function Chinese Comments Design

## Context

The previous rollout added Chinese module comments and high-risk side-effect comments across production business code. The remaining gap is explicit: business classes and functions also need standard Chinese comments.

This is a documentation-coverage change, not a behavior change. The comments should help maintainers understand business intent without turning obvious syntax into noise.

## Decision

Extend the existing Chinese comment standard to cover named business declarations:

- Python `class`, `def`, and `async def` declarations in included business files need a Chinese docstring.
- JavaScript, TypeScript, TSX, and Vue named function declarations or exported function declarations need a nearby Chinese comment.
- Device automation named functions need a nearby Chinese comment because these functions often wrap user-visible Douyin actions.

Do not require comments for anonymous callbacks, inline lambdas, tiny arrow handlers, or generated/static code. Those are not stable business API boundaries and forcing comments there would make the code harder to read.

## Scope

Use the same production business inventory as `scripts/check_chinese_comments.py`:

- `server/app/domains/**/*.py`
- `server/app/main.py`
- `server/app/models/**/*.py`
- `server/app/utils/**/*.py`
- `web/src/**/*.vue`
- `web/src/**/*.js`
- `web/src/**/*.ts`
- `web/src/**/*.tsx`
- `device/main.js`
- `device/config.js`
- `device/core/**/*.js`
- `device/handlers/**/*.js`
- `device/utils/**/*.js`

Keep existing exclusions for tests, spike code, generated files, static assets, package files, docs, caches, and build outputs.

## Comment Standard

Python:

```python
class VideoProductionRun(BaseModel):
    """视频生产运行响应模型，承载前端展示生产进度所需的核心字段。"""
```

```python
async def run_style_lock_worker_step(...):
    """执行一次风格锁定后台任务租约，推进待处理系列的风格资产生成。"""
```

JavaScript/Vue/TypeScript:

```js
// 创建视频生产运行，把系列和剧集绑定到后端生产计划。
export function createVideoProductionRun(seriesId, episodeId) {
  ...
}
```

Device scripts:

```js
// 点击搜索结果进入用户主页，失败时回退到下一条候选结果。
SearchBaseHandler._clickSearchResult = function (index) {
  ...
}
```

Comments should be concise Simplified Chinese and describe the business action, data contract, workflow role, or safety boundary. Do not add comments that merely restate syntax.

## Verification

Extend `scripts/check_chinese_comments.py` with declaration coverage:

1. Python parser uses `ast` to find classes and functions, then checks their docstrings for Chinese.
2. JS/Vue/TS checker uses conservative line-based matching for named declarations:
   - `function name(...)`
   - `export function name(...)`
   - `async function name(...)`
   - `Name.prototype.method = function (...)`
   - `Name.method = function (...)`
   - `const name = function (...)`
3. The checker reports missing declaration comments by file, line, and declaration name.
4. The existing project-level regression test asserts zero module, risk, and declaration gaps.

## Acceptance Criteria

- Every included Python class/function has a Chinese docstring.
- Every included named JS/Vue/TS/device business function has a nearby Chinese comment.
- Anonymous callbacks and inline arrow functions are not mandatory.
- Existing module and high-risk checks continue to pass.
- The checker reports declaration gaps and is covered by focused tests.
- Final strict verification reports zero gaps.

## Self-Review

- No placeholders remain.
- Scope matches the user's explicit class/function requirement without expanding into anonymous callbacks.
- Verification is concrete and can fail on future un-commented declarations.
- The design keeps comments useful enough while allowing automated coverage.
