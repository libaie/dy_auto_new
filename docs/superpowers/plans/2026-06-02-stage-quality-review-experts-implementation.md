# Stage Quality Review Experts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current active `reality_checker` quality gate with seven stage-specific quality reviewer experts while preserving old `reality_checker` invocations as read-only historical audit records.

**Architecture:** Keep the current embedded expert-team architecture and make this a contract change across the manifest, stage DAG, versioned agency team, console payload, and frontend display. Current expert data comes from the manifest and `STAGE_DAG`; historical `reality_checker` data is handled through a legacy read-only path and never participates in current orchestration.

**Canonical display contract:** Use `display_scope: "current_team"` for current experts and `display_scope: "historical_audit"` for legacy audit records. Do not introduce alternate scope strings such as `"historical"` in frontend filters or backend tests.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Vitest, Three.js, local markdown expert profiles.

---

## Scope

This plan implements the confirmed `HOLD SCOPE` path from [2026-06-02-stage-quality-review-experts-design.md](/D:/devWorkspace/jsProjects/dy_auto/docs/superpowers/specs/2026-06-02-stage-quality-review-experts-design.md:406).

In scope:

- Add seven embedded QA expert markdown files.
- Update manifest and strict manifest validation to the current 14-expert team.
- Keep `reality_checker` out of all current team and current stage outputs.
- Support `reality_checker` only as legacy read-only expert detail for historical audit.
- Make manifest/hash failures single configuration blockers.
- Keep provider/API-key/base-url/model errors redacted in user-facing payloads.
- Update frontend current team, historical log, drawer, 2D map, 3D map, and tests.

Out of scope:

- Dynamic expert registry.
- Expert management UI.
- New database tables.
- 3D visual redesign.
- Provider protocol changes.

## File Structure

Create:

- `server/app/data/agency_agents_zh/video-quality/style-lock-quality-reviewer.md`
  Stage-specific quality profile for style lock.
- `server/app/data/agency_agents_zh/video-quality/storyboard-quality-reviewer.md`
  Stage-specific quality profile for storyboard.
- `server/app/data/agency_agents_zh/video-quality/image-stage-quality-reviewer.md`
  Stage-specific quality profile for image generation requests.
- `server/app/data/agency_agents_zh/video-quality/image-review-quality-reviewer.md`
  Stage-specific quality profile for image review.
- `server/app/data/agency_agents_zh/video-quality/video-stage-quality-reviewer.md`
  Stage-specific quality profile for video generation requests.
- `server/app/data/agency_agents_zh/video-quality/video-review-quality-reviewer.md`
  Stage-specific quality profile for video review.
- `server/app/data/agency_agents_zh/video-quality/compose-quality-reviewer.md`
  Stage-specific quality profile for final compose.
- `server/app/data/agency_agents_zh/README.md`
  Maintainer notes for adding or updating embedded experts.
- `web/src/components/agency/agencyExpertLabels.js`
  Shared frontend fallback labels, avatars, role labels, phase labels, and skill summaries.

Modify:

- `server/app/data/agency_agents_zh/manifest.json`
  Current manifest list becomes 14 experts; `reality_checker` is removed from current manifest.
- `server/app/services/agency_manifest.py`
  Current expert ids, legacy expert support, manifest verification behavior.
- `server/app/routers/agency.py`
  Legacy read-only expert detail and redacted user-facing expert errors.
- `server/app/services/agency_orchestrator.py`
  Stage DAG QA assignments and single configuration blocker behavior.
- `server/app/services/video_agency_team.py`
  Team version, roles, quality gates, and `build_agency_context()` role briefs.
- `server/app/services/agency_console.py`
  Current team display, legacy decision log semantics, QA output fields, redaction.
- `server/app/services/agency_contracts.py`
  Optional contract fields for `legacy`, QA output summaries, and current-vs-history display metadata.
- `server/tests/test_agency_manifest.py`
  Current manifest, legacy markdown, hash, and directory tests.
- `server/tests/test_agency_api.py`
  Legacy expert detail, unknown expert 404, redaction tests.
- `server/tests/test_agency_orchestrator.py`
  Stage QA topology and configuration blocker tests.
- `server/tests/test_agency_console.py`
  Current team vs historical audit split and QA output tests.
- `server/tests/test_series_style_lock_pipeline.py`
  Team upgrade expectations.
- `web/src/components/agency/AgencyInvocationGraph.vue`
  Use shared labels and show current QA experts.
- `web/src/components/agency/AgencyTeamMap2D.vue`
  Use shared labels and handle 14 current experts.
- `web/src/components/agency/AgencyTeamMap3D.vue`
  Use shared labels and keep inactive QA experts from lighting up.
- `web/src/components/agency/AgencyExpertDrawer.vue`
  Display legacy badge, QA metadata, and localized error text.
- `web/src/components/agency/AgencyDecisionLog.vue`
  Render responsive decision cards/table, mark legacy audit records, and expose QA fields as readable Chinese review sections.
- `web/src/views/AgencyConsolePage.vue`
  Ensure current team, historical log, and console metrics remain visually separate; remove stale 8-expert copy.
- `web/src/__tests__/agency-console-page.test.js`
  Current team and quality gate expectations.
- `web/src/__tests__/agency-control-room.test.js`
  Stage graph mock expectations.
- `web/src/__tests__/agency-3d-fallback.test.js`
  14 expert display and active QA tests.
- `web/src/__tests__/agency-expert-drawer.test.js`
  Legacy drawer and QA drawer tests.
- `web/src/__tests__/agency-api.test.js`
  Existing route tests remain valid.

---

### Task 1: Backend Manifest Contract And QA Markdown

**Files:**

- Create: `server/app/data/agency_agents_zh/video-quality/style-lock-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/video-quality/storyboard-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/video-quality/image-stage-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/video-quality/image-review-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/video-quality/video-stage-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/video-quality/video-review-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/video-quality/compose-quality-reviewer.md`
- Create: `server/app/data/agency_agents_zh/README.md`
- Modify: `server/app/data/agency_agents_zh/manifest.json`
- Modify: `server/app/services/agency_manifest.py`
- Test: `server/tests/test_agency_manifest.py`

- [ ] **Step 1: Replace the manifest team test with the current 14-expert contract**

Edit `server/tests/test_agency_manifest.py` so `test_manifest_contains_exact_video_expert_team()` asserts this exact list:

```python
def test_manifest_contains_exact_video_expert_team():
    experts = list_experts()
    assert [expert.expert_id for expert in experts] == [
        "narrative_designer",
        "visual_storyteller",
        "image_prompt_engineer",
        "prompt_engineer",
        "short_video_editing_coach",
        "douyin_strategist",
        "video_optimization_specialist",
        "style_lock_quality_reviewer",
        "storyboard_quality_reviewer",
        "image_stage_quality_reviewer",
        "image_review_quality_reviewer",
        "video_stage_quality_reviewer",
        "video_review_quality_reviewer",
        "compose_quality_reviewer",
    ]
    assert set(EXPERT_IDS) == {expert.expert_id for expert in experts}
    assert "reality_checker" not in EXPERT_IDS
```

- [ ] **Step 2: Add manifest tests for QA metadata and legacy markdown**

Append these tests to `server/tests/test_agency_manifest.py`:

```python
def test_quality_reviewers_are_stage_scoped_quality_roles():
    expected = {
        "style_lock_quality_reviewer": ("video-quality/style-lock-quality-reviewer.md", ["style_lock"]),
        "storyboard_quality_reviewer": ("video-quality/storyboard-quality-reviewer.md", ["storyboard"]),
        "image_stage_quality_reviewer": ("video-quality/image-stage-quality-reviewer.md", ["image_stage"]),
        "image_review_quality_reviewer": ("video-quality/image-review-quality-reviewer.md", ["image_review"]),
        "video_stage_quality_reviewer": ("video-quality/video-stage-quality-reviewer.md", ["video_stage"]),
        "video_review_quality_reviewer": ("video-quality/video-review-quality-reviewer.md", ["video_review"]),
        "compose_quality_reviewer": ("video-quality/compose-quality-reviewer.md", ["compose"]),
    }
    by_id = {expert.expert_id: expert for expert in list_experts()}

    for expert_id, (source_path, phases) in expected.items():
        expert = by_id[expert_id]
        assert expert.role_type == "quality"
        assert expert.source_path == source_path
        assert expert.phases == phases


def test_legacy_reality_checker_markdown_is_read_only_not_current():
    legacy = get_legacy_expert("reality_checker")
    assert legacy.expert_id == "reality_checker"
    assert legacy.legacy is True
    assert legacy.source_path == "testing/testing-reality-checker.md"
    assert "reality_checker" not in [expert.expert_id for expert in list_experts()]

    markdown = read_legacy_expert_markdown("reality_checker")
    assert len(markdown) > 500
    assert "reality" in markdown.lower() or "现实" in markdown


def test_read_current_expert_markdown_rejects_legacy_expert():
    with pytest.raises(AgencyManifestError, match="unknown agency expert"):
        read_expert_markdown("reality_checker")
```

Update the import list at the top of the file:

```python
from app.services.agency_manifest import (
    AgencyManifest,
    EXPERT_IDS,
    AgencyManifestError,
    get_expert,
    get_legacy_expert,
    list_experts,
    read_expert_markdown,
    read_legacy_expert_markdown,
    verify_manifest,
)
```

- [ ] **Step 3: Update the directory test to allow current and legacy markdown**

Replace `test_vendored_expert_directory_contains_only_current_manifest_markdown()` with:

```python
def test_vendored_expert_directory_contains_only_current_and_legacy_markdown():
    expected_paths = {(DATA_ROOT / expert.source_path).resolve() for expert in list_experts()}
    expected_paths.add((DATA_ROOT / "testing/testing-reality-checker.md").resolve())
    expected_paths.add((DATA_ROOT / "README.md").resolve())
    actual_paths = {path.resolve() for path in DATA_ROOT.rglob("*.md")}

    assert actual_paths == expected_paths
```

- [ ] **Step 4: Run manifest tests and verify they fail for missing implementation**

Run:

```powershell
pytest server/tests/test_agency_manifest.py -q
```

Expected: failure because `get_legacy_expert` is not defined, `EXPERT_IDS` still contains `reality_checker`, and the seven QA markdown files do not exist.

- [ ] **Step 5: Add current and legacy manifest support**

In `server/app/services/agency_manifest.py`, replace `EXPERT_IDS` and add a legacy model:

```python
EXPERT_IDS = (
    "narrative_designer",
    "visual_storyteller",
    "image_prompt_engineer",
    "prompt_engineer",
    "short_video_editing_coach",
    "douyin_strategist",
    "video_optimization_specialist",
    "style_lock_quality_reviewer",
    "storyboard_quality_reviewer",
    "image_stage_quality_reviewer",
    "image_review_quality_reviewer",
    "video_stage_quality_reviewer",
    "video_review_quality_reviewer",
    "compose_quality_reviewer",
)


class LegacyAgencyExpertSource(AgencyExpertSource):
    legacy: bool = True


LEGACY_EXPERTS = {
    "reality_checker": LegacyAgencyExpertSource(
        expert_id="reality_checker",
        name_zh="历史审计角色",
        role_type="legacy",
        source_path="testing/testing-reality-checker.md",
        sha256="",
        phases=[],
        legacy=True,
    )
}
```

Add these functions below `get_expert()`:

```python
def get_legacy_expert(expert_id: str) -> LegacyAgencyExpertSource:
    try:
        return LEGACY_EXPERTS[expert_id]
    except KeyError as exc:
        raise AgencyManifestError(f"unknown legacy agency expert: {expert_id}") from exc


def read_legacy_expert_markdown(expert_id: str) -> str:
    expert = get_legacy_expert(expert_id)
    path = _expert_path(expert)
    if not path.is_file():
        raise AgencyManifestError(f"legacy expert markdown not found: {expert.source_path}")
    return path.read_text(encoding="utf-8")
```

Keep `list_experts()` current-only. Do not add legacy experts to `load_manifest()`.

- [ ] **Step 6: Create the seven QA markdown files**

Create `server/app/data/agency_agents_zh/video-quality/style-lock-quality-reviewer.md`:

```markdown
---
name: 风格锁定质量审查专家
description: 针对风格锁定阶段的质量门禁专家，基于证据判断系列是否具备批量生产的一致性基础。
emoji: 🎬
color: emerald
---

# 风格锁定质量审查专家

## 你的身份与记忆

你只负责风格锁定质量审查。你不替代创作专家，不重写故事，不决定最终人工放行。你检查风格圣经是否足够支撑后续批量视频生成。

## 核心使命

确认角色规则、场景规则、视觉风格、声音包装、字幕/BGM 包装、参考图 URL、缺失资产和版本锁定状态是否完整、明确、可执行。

## 强制流程

1. 读取 `style_lock`、角色、场景、参考图和 `missing_assets`。
2. 检查角色身份、外观、服装、声音策略、参考图是否完整。
3. 检查场景位置、光线、氛围、参考图是否完整。
4. 检查视觉风格是否包含色彩、镜头、材质、光影约束。
5. 输出是否通过，以及必须补齐的资产。

## 审查清单

- 角色有稳定身份、外观、服装和参考图。
- 场景有稳定地点、光影、氛围和参考图。
- 视觉风格不是抽象形容词，而是可执行约束。
- 字幕、BGM、片头片尾、水印策略清楚。
- `missing_assets` 被明确记录。
- 版本号和锁定状态清楚。

## 自动阻断条件

- 任一主要角色缺少身份、外观、服装或参考图。
- 任一核心场景缺少地点、光影、氛围或参考图。
- 视觉风格只含抽象形容词，没有可执行约束。
- 存在缺失资产但没有写入 `missing_assets`。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

直接、具体、引用证据。不要使用“整体不错”这类无法执行的评价。

## 成功指标

后续分镜、图像和视频生成可以稳定继承同一套角色、场景、视觉和包装规则。
```

Create `server/app/data/agency_agents_zh/video-quality/storyboard-quality-reviewer.md`:

```markdown
---
name: 分镜脚本质量审查专家
description: 针对自动分镜阶段的质量门禁专家，检查分镜是否可执行、连续、可生产。
emoji: 🎬
color: emerald
---

# 分镜脚本质量审查专家

## 你的身份与记忆

你只负责分镜质量审查。你不替代叙事设计师，不重写剧情，不负责最终人工放行。你判断每个 frame 是否能进入图像和视频生产。

## 核心使命

确认分镜包含 `character_ids`、`scene_id`、`reference_urls`、`image_prompt`、`narration`、`duration`、`audio_mode`、`continuity_notes`，并且镜头节奏、动作、情绪和连续性清楚。

## 强制流程

1. 读取锁定风格圣经和 storyboard frames。
2. 逐帧检查必填字段。
3. 检查角色和场景是否引用已锁定资产。
4. 检查长视频是否有段落拆分和连续性说明。
5. 输出阻断项和可执行修改。

## 审查清单

- 每个 frame 字段完整。
- 首帧具备清晰钩子。
- 镜头动作、情绪和时长可执行。
- 分镜没有发明未锁定角色或场景。
- 长视频分段和衔接说明清楚。

## 自动阻断条件

- 任一 frame 缺少必填字段。
- 任一 frame 引用未锁定角色或场景。
- 镜头动作、情绪或时长不可执行。
- 长视频缺少清晰段落或连续性说明。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

按 frame 指出问题，说明为什么会影响后续生产。

## 成功指标

每个 frame 都能直接进入图像生成和视频生成，且故事连续性不靠人工猜测。
```

Create `server/app/data/agency_agents_zh/video-quality/image-stage-quality-reviewer.md`:

```markdown
---
name: 图像生成质量审查专家
description: 针对图像生成请求阶段的质量门禁专家，检查 prompt、参考图和 provider 参数是否稳定。
emoji: 🎬
color: emerald
---

# 图像生成质量审查专家

## 你的身份与记忆

你只负责图像生成请求质量审查。你不评价最终图片好坏，只判断请求是否足够稳定，能生成符合风格锁定的画面。

## 核心使命

确认每个图像请求携带锁定角色、场景和视觉参考图，prompt 保留身份锚点、镜头、构图、光影和 provider 参数约束。

## 强制流程

1. 读取 frame、reference_urls、image_prompt 和 provider options。
2. 检查 prompt 是否引用锁定资产，而不是重新发明角色或场景。
3. 检查角色身份、服装、发型和视觉风格锚定语。
4. 检查 provider 参数是否与目标场景和模型能力匹配。
5. 输出可执行的补充 prompt 或参数修改。

## 审查清单

- 图像请求包含 `reference_urls`。
- prompt 包含角色身份锚定。
- prompt 包含场景和光影约束。
- provider 参数不与目标用途冲突。
- 多参考图用途清楚。

## 自动阻断条件

- 图像请求没有参考图。
- prompt 重新发明角色或场景。
- 缺少角色身份锚定或风格锚定。
- provider 参数与模型能力或目标用途冲突。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

用可复制进 prompt 或 provider options 的方式描述修改。

## 成功指标

图像生成请求稳定继承锁定角色、场景和视觉风格，减少身份漂移。
```

Create `server/app/data/agency_agents_zh/video-quality/image-review-quality-reviewer.md`:

```markdown
---
name: 图像结果质量审查专家
description: 针对图片结果审查阶段的质量门禁专家，判断图片是否可进入图生视频阶段。
emoji: 🎬
color: emerald
---

# 图像结果质量审查专家

## 你的身份与记忆

你只负责图片结果质量审查。你不替代人工最终放行，但你必须指出图片能否作为图生视频输入。

## 核心使命

确认图片保持角色长相、服装、场景、光影、美学风格和构图一致，且人工或 AI 审查证据足够。

## 强制流程

1. 读取生成图片、参考图、frame 和审查记录。
2. 检查角色身份和服装是否漂移。
3. 检查场景和风格是否冲突。
4. 检查畸变、遮挡、构图不可用等问题。
5. 输出改图、重绘或进入下一阶段的建议。

## 审查清单

- 角色身份稳定。
- 服装和发型与锁定规则一致。
- 场景和光影与锁定规则一致。
- 构图能支撑下一步图生视频。
- 审查证据足够。

## 自动阻断条件

- 角色身份明显漂移。
- 场景或风格与锁定规则冲突。
- 图片存在明显畸变、遮挡或构图不可用。
- 无法证明参考图被遵守。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

明确指出需要改图、重绘还是可进入图生视频。

## 成功指标

通过的图片可作为稳定图生视频输入，不把明显漂移带入视频阶段。
```

Create `server/app/data/agency_agents_zh/video-quality/video-stage-quality-reviewer.md`:

```markdown
---
name: 视频生成质量审查专家
description: 针对图生视频请求阶段的质量门禁专家，检查首尾帧、动作、镜头和连续性是否可生成稳定片段。
emoji: 🎬
color: emerald
---

# 视频生成质量审查专家

## 你的身份与记忆

你只负责视频生成请求质量审查。你不评价最终片段质量，只判断视频请求是否足够明确和稳定。

## 核心使命

确认图生视频请求携带 approved image references、动作、情绪、镜头运动、时长、上一段结束状态和下一段衔接说明。

## 强制流程

1. 读取 approved images、frame、video prompt 和 provider options。
2. 检查首帧和结束状态是否清楚。
3. 检查动作、情绪和镜头运动是否可执行。
4. 检查片段时长是否处在 provider 稳定范围。
5. 输出重写 prompt 或拆分片段建议。

## 审查清单

- 视频请求包含 approved image references。
- 动作、情绪、镜头运动清楚。
- 时长合理。
- 长视频片段有前后衔接说明。
- 请求不试图一次生成超过 provider 稳定范围的长片段。

## 自动阻断条件

- 缺少 approved image references。
- 动作、情绪或镜头运动不清楚。
- 缺少上一段结束状态或下一段衔接说明。
- 请求一次性生成过长片段。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

用导演式语言指出动作、镜头和衔接需要如何修改。

## 成功指标

视频请求能生成稳定短片段，并能与前后片段连续。
```

Create `server/app/data/agency_agents_zh/video-quality/video-review-quality-reviewer.md`:

```markdown
---
name: 视频结果质量审查专家
description: 针对视频片段结果审查阶段的质量门禁专家，判断片段是否可进入最终合成。
emoji: 🎬
color: emerald
---

# 视频结果质量审查专家

## 你的身份与记忆

你只负责视频片段结果质量审查。你不替代人工最终放行，但必须判断片段能否进入合成。

## 核心使命

确认视频片段保持角色身份、动作连续、镜头稳定、衔接点可用，没有明显变形、闪烁、穿模或风格漂移。

## 强制流程

1. 读取视频片段、frame、approved image 和审查记录。
2. 检查角色脸部、服装和体型是否漂移。
3. 检查动作和镜头是否稳定。
4. 检查片段结尾是否能衔接下一段。
5. 输出重生成或进入合成的判断。

## 审查清单

- 角色身份稳定。
- 动作没有明显变形。
- 镜头没有不可用抖动。
- 片段时长符合计划。
- 结尾衔接点清楚。
- 人工审查要求已满足。

## 自动阻断条件

- 角色脸部、服装或体型明显漂移。
- 动作变形、穿模、闪烁或镜头不可用。
- 片段结尾无法衔接下一段。
- 必要人工审查未完成。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

指出具体时间点、画面问题和重生成方向。

## 成功指标

通过的视频片段能进入最终合成，不把明显运动缺陷带入成片。
```

Create `server/app/data/agency_agents_zh/video-quality/compose-quality-reviewer.md`:

```markdown
---
name: 合成交付质量审查专家
description: 针对最终合成阶段的质量门禁专家，判断成片是否可写回剧集和视频资产库。
emoji: 🎬
color: emerald
---

# 合成交付质量审查专家

## 你的身份与记忆

你只负责最终合成交付质量审查。你不替代人工最终放行，但必须确认写回资产库前的交付条件。

## 核心使命

确认字幕、BGM、片头片尾、水印、输出规格、节奏、最终视频 URL、duration、edit manifest、Episode 和 GeneratedVideo 写回条件完整。

## 强制流程

1. 读取 edit manifest、final video、episode 和 generated video output。
2. 检查字幕、BGM、水印和输出规格是否符合锁定包装。
3. 检查最终视频是否可播放、已持久化、duration 合理。
4. 检查 Episode 和 GeneratedVideo 写回条件。
5. 输出是否允许写回资产库。

## 审查清单

- edit manifest 存在。
- 输出规格清楚。
- 字幕/BGM/片头片尾/水印符合锁定包装。
- 最终视频可播放且已持久化。
- Episode 和 GeneratedVideo 写回字段完整。
- 最终人工审查要求已满足。

## 自动阻断条件

- 缺少 edit manifest 或输出规格。
- 字幕/BGM/水印策略与锁定包装冲突。
- 最终视频未持久化或不可播放。
- 未通过最终人工审查却尝试写回。

## 输出模板

输出 JSON，字段必须包含 `decision`、`findings`、`required_changes`、`evidence`、`next_action`。`decision` 只能是 `passed`、`warn`、`blocked` 或 `failed`。

## 沟通风格

以交付清单方式说明是否可以写回，以及缺哪一项。

## 成功指标

最终成片能安全写回剧集和视频资产库，用户能追踪成片质量依据。
```

- [ ] **Step 7: Add the expert maintainer README**

Create `server/app/data/agency_agents_zh/README.md`:

```markdown
# Embedded Agency Experts

This directory contains the current embedded expert team used by `dy_auto`.

Current experts are listed in `manifest.json` and must match `app.services.agency_manifest.EXPERT_IDS` exactly.

When adding or changing an expert:

1. Add or edit the markdown file inside this directory.
2. Recompute the sha256 using PowerShell:

   ```powershell
   @'
   import hashlib
   from pathlib import Path
   for path in sorted(Path("server/app/data/agency_agents_zh").rglob("*.md")):
       if path.name == "README.md":
           continue
       print(path.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
   '@ | python -
   ```

3. Update `manifest.json`.
4. Update `EXPERT_IDS` if this is a current expert.
5. Keep legacy experts out of `EXPERT_IDS`.
6. Run:

   ```powershell
   pytest server/tests/test_agency_manifest.py -q
   ```
```

- [ ] **Step 8: Update manifest.json with current experts and computed hashes**

Run this helper after the markdown files exist:

```powershell
@'
import hashlib
from pathlib import Path
root = Path("server/app/data/agency_agents_zh")
for rel in [
    "game-development/narrative-designer.md",
    "design/design-visual-storyteller.md",
    "design/design-image-prompt-engineer.md",
    "specialized/prompt-engineer.md",
    "marketing/marketing-short-video-editing-coach.md",
    "marketing/marketing-douyin-strategist.md",
    "marketing/marketing-video-optimization-specialist.md",
    "video-quality/style-lock-quality-reviewer.md",
    "video-quality/storyboard-quality-reviewer.md",
    "video-quality/image-stage-quality-reviewer.md",
    "video-quality/image-review-quality-reviewer.md",
    "video-quality/video-stage-quality-reviewer.md",
    "video-quality/video-review-quality-reviewer.md",
    "video-quality/compose-quality-reviewer.md",
]:
    print(rel, hashlib.sha256((root / rel).read_bytes()).hexdigest())
'@ | python -
```

Update `server/app/data/agency_agents_zh/manifest.json` with 14 entries in the same order as `EXPERT_IDS`. Use these `name_zh`, `role_type`, and `phases` values for the new entries:

```json
[
  {
    "expert_id": "style_lock_quality_reviewer",
    "name_zh": "风格锁定质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/style-lock-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["style_lock"]
  },
  {
    "expert_id": "storyboard_quality_reviewer",
    "name_zh": "分镜脚本质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/storyboard-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["storyboard"]
  },
  {
    "expert_id": "image_stage_quality_reviewer",
    "name_zh": "图像生成质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/image-stage-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["image_stage"]
  },
  {
    "expert_id": "image_review_quality_reviewer",
    "name_zh": "图像结果质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/image-review-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["image_review"]
  },
  {
    "expert_id": "video_stage_quality_reviewer",
    "name_zh": "视频生成质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/video-stage-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["video_stage"]
  },
  {
    "expert_id": "video_review_quality_reviewer",
    "name_zh": "视频结果质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/video-review-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["video_review"]
  },
  {
    "expert_id": "compose_quality_reviewer",
    "name_zh": "合成交付质量审查专家",
    "role_type": "quality",
    "source_path": "video-quality/compose-quality-reviewer.md",
    "sha256": "<computed hash>",
    "phases": ["compose"]
  }
]
```

Replace each `<computed hash>` with the actual sha256 printed by the helper before saving.

- [ ] **Step 9: Run manifest tests**

Run:

```powershell
pytest server/tests/test_agency_manifest.py -q
```

Expected: all tests in `server/tests/test_agency_manifest.py` pass.

- [ ] **Step 10: Commit manifest and markdown changes**

Run:

```powershell
git add server/app/data/agency_agents_zh server/app/services/agency_manifest.py server/tests/test_agency_manifest.py
git commit -m "feat: add stage-specific quality reviewer experts"
```

---

### Task 2: Legacy Expert API And Redacted Expert Errors

**Files:**

- Modify: `server/app/routers/agency.py`
- Modify: `server/app/services/agency_contracts.py`
- Test: `server/tests/test_agency_api.py`

- [ ] **Step 1: Add API tests for legacy expert detail**

Append to `server/tests/test_agency_api.py`:

```python
def test_get_legacy_reality_checker_expert_returns_read_only_payload(client):
    response = client.get("/api/agency/experts/reality_checker")

    assert response.status_code == 200
    data = response.json()
    assert data["expert_id"] == "reality_checker"
    assert data["name"] == "历史审计角色"
    assert data["role_type"] == "legacy"
    assert data["legacy"] is True
    assert data["phases"] == []
    assert "历史审计记录" in data["markdown"]
    assert "不参与当前编排" in data["markdown"]


def test_get_unknown_expert_still_returns_404(client):
    response = client.get("/api/agency/experts/unknown_quality_reviewer")

    assert response.status_code == 404
    assert "unknown" in response.json()["detail"].lower()
```

- [ ] **Step 2: Add API tests for redacted invocation detail**

Append to `server/tests/test_agency_api.py`:

```python
def test_get_invocation_detail_redacts_provider_secrets(client, db):
    series = Series(title="Secret Series", logline="Secret logline", genre="drama")
    db.add(series)
    db.flush()
    row = AgencyExpertInvocation(
        idempotency_key=f"secret-{series.id}",
        series_id=series.id,
        stage="storyboard",
        expert_id="storyboard_quality_reviewer",
        role="qa",
        execution_status="failed",
        result_status="failed",
        output_summary_json={"decision": "blocked"},
        evidence_json=[],
        source_repo="test",
        source_commit="test",
        source_path="video-quality/storyboard-quality-reviewer.md",
        source_sha256="a" * 64,
        model_config_snapshot_json={
            "api_key": "ark-secret-value",
            "headers": {"Authorization": "Bearer secret-token"},
            "provider_payload": {"prompt": "safe summary only"},
        },
        error_message="Provider authorization failed",
    )
    db.add(row)
    db.commit()

    response = client.get(f"/api/agency/invocations/{row.id}")

    assert response.status_code == 200
    text = response.text
    assert "ark-secret-value" not in text
    assert "secret-token" not in text
    assert "Bearer" not in text
    assert response.json()["model_config_snapshot"]["api_key"] == "[REDACTED]"
```

Ensure `Series` is imported in this test file:

```python
from app.db_models import AgencyExpertInvocation, Episode, PipelineRun, Series, VideoProductionRun
```

- [ ] **Step 3: Run API tests and verify they fail for missing legacy route**

Run:

```powershell
pytest server/tests/test_agency_api.py -q
```

Expected: legacy expert test fails because the router currently returns 404 for `reality_checker`.

- [ ] **Step 4: Implement legacy read-only expert detail**

In `server/app/routers/agency.py`, update the import:

```python
from app.services.agency_manifest import (
    AgencyManifestError,
    get_expert,
    get_legacy_expert,
    list_experts,
    load_manifest,
    read_expert_markdown,
    read_legacy_expert_markdown,
)
```

Add this helper below `_expert_summary()`:

```python
def _legacy_expert_summary(expert) -> dict:
    return {
        "expert_id": expert.expert_id,
        "name": expert.name_zh,
        "role_type": expert.role_type,
        "source_path": expert.source_path,
        "source_commit": "legacy",
        "sha256": expert.sha256 or "",
        "phases": expert.phases,
        "legacy": True,
    }
```

Replace `get_agency_expert()` with:

```python
@router.get("/experts/{expert_id}")
def get_agency_expert(expert_id: str, _=Depends(require_role("admin"))):
    if not _EXPERT_ID_RE.fullmatch(expert_id):
        raise HTTPException(status_code=400, detail="Invalid expert id")
    try:
        expert = get_expert(expert_id)
        data = _expert_summary(expert)
        data["legacy"] = False
        data["markdown"] = read_expert_markdown(expert_id)
        return data
    except AgencyManifestError:
        try:
            legacy = get_legacy_expert(expert_id)
            data = _legacy_expert_summary(legacy)
            legacy_markdown = read_legacy_expert_markdown(expert_id)
            data["markdown"] = (
                "# 历史审计角色\n\n"
                "这是历史审计记录，不参与当前编排。\n\n"
                f"{legacy_markdown}"
            )
            return data
        except AgencyManifestError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 5: Update contracts for optional legacy metadata**

In `server/app/services/agency_contracts.py`, add optional fields to `AgencyExpertSummary`:

```python
from typing import Literal


class AgencyExpertSummary(BaseModel):
    expert_id: str
    name: str
    role_type: str
    source_path: str
    source_commit: str
    sha256: str
    phases: list[str]
    legacy: bool = False
```

Also extend `AgencyInvocationSummary` so FastAPI response validation catches missing QA fields before the frontend does:

```python
class AgencyInvocationSummary(BaseModel):
    id: str
    stage: str
    expert_id: str
    role: str
    execution_status: AgencyExecutionStatus
    result_status: AgencyInvocationResultStatus
    summary: str = ""
    decision: str = ""
    findings: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_action: str = ""
    legacy: bool = False
    display_scope: Literal["current_team", "historical_audit"] = "current_team"
    duration_ms: int = 0
    error_code: str | None = None
```

Add a typed decision-log contract:

```python
class AgencyDecisionLogItem(BaseModel):
    id: str
    invocation_id: str
    stage: str
    expert_id: str
    role: str
    result_status: AgencyInvocationResultStatus
    decision: str = ""
    findings: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    next_action: str = ""
    error_code: str | None = None
    legacy: bool = False
    display_scope: Literal["current_team", "historical_audit"] = "current_team"
```

Then replace only the existing `decision_log` field in `AgencyConsoleResponse`:

```python
# before
decision_log: list[dict[str, Any]]

# after
decision_log: list[AgencyDecisionLogItem]
```

Console summaries must expose user-readable `evidence: list[str]`. Keep raw object evidence only in `/api/agency/invocations/{id}` detail payload.

- [ ] **Step 6: Run API tests**

Run:

```powershell
pytest server/tests/test_agency_api.py -q
```

Expected: all tests in `server/tests/test_agency_api.py` pass.

- [ ] **Step 7: Commit API changes**

Run:

```powershell
git add server/app/routers/agency.py server/app/services/agency_contracts.py server/tests/test_agency_api.py
git commit -m "feat: support legacy agency expert audit detail"
```

---

### Task 3: Stage DAG, Single QA Invocation, And Configuration Blockers

**Files:**

- Modify: `server/app/services/agency_orchestrator.py`
- Test: `server/tests/test_agency_orchestrator.py`

- [ ] **Step 1: Replace the stage DAG topology test**

In `server/tests/test_agency_orchestrator.py`, replace `test_stage_dag_has_expected_video_production_topology()` with:

```python
def test_stage_dag_has_expected_video_production_topology():
    assert STAGE_DAG == {
        "style_lock": {
            "reviewers": ["image_prompt_engineer", "short_video_editing_coach"],
            "lead": "visual_storyteller",
            "qa": ["style_lock_quality_reviewer"],
        },
        "storyboard": {
            "reviewers": ["visual_storyteller", "short_video_editing_coach", "douyin_strategist"],
            "lead": "narrative_designer",
            "qa": ["storyboard_quality_reviewer"],
        },
        "image_stage": {
            "reviewers": ["visual_storyteller", "prompt_engineer"],
            "lead": "image_prompt_engineer",
            "qa": ["image_stage_quality_reviewer"],
        },
        "image_review": {
            "reviewers": ["image_prompt_engineer"],
            "lead": "visual_storyteller",
            "qa": ["image_review_quality_reviewer"],
        },
        "video_stage": {
            "reviewers": ["prompt_engineer", "visual_storyteller"],
            "lead": "short_video_editing_coach",
            "qa": ["video_stage_quality_reviewer"],
        },
        "video_review": {
            "reviewers": ["video_optimization_specialist"],
            "lead": "short_video_editing_coach",
            "qa": ["video_review_quality_reviewer"],
        },
        "compose": {
            "reviewers": ["douyin_strategist", "video_optimization_specialist"],
            "lead": "short_video_editing_coach",
            "qa": ["compose_quality_reviewer"],
        },
    }
```

- [ ] **Step 2: Add one-QA-per-stage and no-legacy-current tests**

Append to `server/tests/test_agency_orchestrator.py`:

```python
def test_each_stage_has_exactly_one_stage_specific_quality_reviewer():
    expected_qa = {
        "style_lock": "style_lock_quality_reviewer",
        "storyboard": "storyboard_quality_reviewer",
        "image_stage": "image_stage_quality_reviewer",
        "image_review": "image_review_quality_reviewer",
        "video_stage": "video_stage_quality_reviewer",
        "video_review": "video_review_quality_reviewer",
        "compose": "compose_quality_reviewer",
    }

    for stage, config in STAGE_DAG.items():
        assert config["qa"] == [expected_qa[stage]]


def test_stage_dag_never_assigns_legacy_reality_checker():
    for roles in STAGE_DAG.values():
        assigned = [*roles["reviewers"], roles["lead"], *roles["qa"]]
        assert "reality_checker" not in assigned
```

- [ ] **Step 3: Update existing runtime-order test expectation**

In `test_reviewers_run_with_bounded_concurrency_before_lead_and_qa()`, update the style lock expectations:

```python
assert [role for role, _expert_id in call_order[:2]] == ["reviewer", "reviewer"]
assert [role for role, _expert_id in call_order[2:]] == ["lead", "qa"]
assert runtime_db_by_role["reviewer"] == [None, None]
assert runtime_db_by_role["lead"] == [None]
assert runtime_db_by_role["qa"] == [None]
```

- [ ] **Step 4: Replace `reality_checker` in stage status precedence test**

In `test_stage_status_precedence_uses_all_invocations()`, replace:

```python
"reality_checker": "blocked",
```

with:

```python
"storyboard_quality_reviewer": "blocked",
```

- [ ] **Step 5: Add config-blocker redaction test**

Append to `server/tests/test_agency_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_missing_openai_runtime_config_returns_redacted_single_blocker(db):
    series = _series(db)
    calls = {"count": 0}

    async def fake_runtime(**kwargs):
        calls["count"] += 1
        return RuntimeResult(expert_id=kwargs["expert_id"])

    orchestrator = AgencyOrchestrator(runtime_invoke=fake_runtime)
    result = await orchestrator.run_storyboard_review(
        db,
        series_id=series.id,
        stage_context={"frames": [{"frame_id": "shot-001"}]},
        runtime_config={
            "provider": "openai-compatible",
            "model": "",
            "base_url": "",
            "api_key": "sk-secret-token",
            "config": {"protocol": "openai_chat_completions"},
        },
    )

    assert result["stage_status"] == "blocked"
    assert result["error_code"] == "EXPERT_MODEL_CONFIG_MISSING"
    assert result["invocation_ids"] == []
    assert result["invocations"] == []
    assert calls["count"] == 0
    assert db.query(AgencyExpertInvocation).count() == 0
    assert "sk-secret-token" not in str(result)
```

- [ ] **Step 6: Run orchestrator tests and verify they fail before implementation**

Run:

```powershell
pytest server/tests/test_agency_orchestrator.py -q
```

Expected: failures where `STAGE_DAG` still references `reality_checker` or omits QA in style lock.

- [ ] **Step 7: Update STAGE_DAG to the stage-specific QA contract**

In `server/app/services/agency_orchestrator.py`, replace the `STAGE_DAG` constant with:

```python
STAGE_DAG = {
    "style_lock": {
        "reviewers": ["image_prompt_engineer", "short_video_editing_coach"],
        "lead": "visual_storyteller",
        "qa": ["style_lock_quality_reviewer"],
    },
    "storyboard": {
        "reviewers": ["visual_storyteller", "short_video_editing_coach", "douyin_strategist"],
        "lead": "narrative_designer",
        "qa": ["storyboard_quality_reviewer"],
    },
    "image_stage": {
        "reviewers": ["visual_storyteller", "prompt_engineer"],
        "lead": "image_prompt_engineer",
        "qa": ["image_stage_quality_reviewer"],
    },
    "image_review": {
        "reviewers": ["image_prompt_engineer"],
        "lead": "visual_storyteller",
        "qa": ["image_review_quality_reviewer"],
    },
    "video_stage": {
        "reviewers": ["prompt_engineer", "visual_storyteller"],
        "lead": "short_video_editing_coach",
        "qa": ["video_stage_quality_reviewer"],
    },
    "video_review": {
        "reviewers": ["video_optimization_specialist"],
        "lead": "short_video_editing_coach",
        "qa": ["video_review_quality_reviewer"],
    },
    "compose": {
        "reviewers": ["douyin_strategist", "video_optimization_specialist"],
        "lead": "short_video_editing_coach",
        "qa": ["compose_quality_reviewer"],
    },
}
```

- [ ] **Step 8: Verify idempotency key length with new longest expert id**

Append to `server/tests/test_agency_orchestrator.py`:

```python
def test_longest_quality_reviewer_idempotency_key_fits_database_column():
    key = "agency:{series}:{scope}:{stage}:{role}:{expert}:{hash}".format(
        series="s" * 36,
        scope="p" * 36,
        stage="image_review",
        role="qa",
        expert="image_review_quality_reviewer",
        hash="h" * 24,
    )

    assert len(key) <= 160
```

- [ ] **Step 9: Run orchestrator tests**

Run:

```powershell
pytest server/tests/test_agency_orchestrator.py -q
```

Expected: all tests in `server/tests/test_agency_orchestrator.py` pass after dependent manifest work from Task 1 is complete.

- [ ] **Step 10: Commit orchestrator changes**

Run:

```powershell
git add server/app/services/agency_orchestrator.py server/tests/test_agency_orchestrator.py
git commit -m "feat: assign stage-specific agency quality reviewers"
```

---

### Task 4: Versioned Agency Team And Agency Context

**Files:**

- Modify: `server/app/services/video_agency_team.py`
- Test: `server/tests/test_agency_orchestrator.py`
- Test: `server/tests/test_series_style_lock_pipeline.py`

- [ ] **Step 1: Add video agency team tests for current roles**

Append to `server/tests/test_agency_orchestrator.py`:

```python
def test_video_agency_team_contains_current_quality_roles_without_legacy():
    team = build_video_agency_team()
    roles = team["core_roles"] + team["support_roles"]
    role_ids = [role["id"] for role in roles]

    assert "reality_checker" not in role_ids
    assert role_ids == list(EXPERT_IDS)
    assert team["version"] >= "2026-06-02"
    assert any(role["id"] == "compose_quality_reviewer" for role in team["support_roles"])
```

Update the imports in `server/tests/test_agency_orchestrator.py`:

```python
from app.services.agency_manifest import EXPERT_IDS, list_experts, load_manifest
from app.services.video_agency_team import build_agency_context, build_video_agency_team, ensure_video_agency_team
```

- [ ] **Step 2: Add context test for QA role briefs**

Append:

```python
def test_agency_context_includes_quality_role_briefs_for_stage_prompts():
    context = build_agency_context({"style_lock": {"locked": True}})
    role_brief_ids = [item["id"] for item in context["role_brief"]]

    assert "style_lock_quality_reviewer" in role_brief_ids
    assert "compose_quality_reviewer" in role_brief_ids
    quality_brief = next(item for item in context["role_brief"] if item["id"] == "style_lock_quality_reviewer")
    assert "mission" in quality_brief
    assert quality_brief["directives"]
```

- [ ] **Step 3: Add team upgrade test for stale reality_checker team**

Append:

```python
def test_ensure_video_agency_team_upgrades_team_containing_legacy_reality_checker():
    style_lock = {
        "agency_team": {
            "enabled": True,
            "version": "2026-06-01.2",
            "core_roles": [{"id": "narrative_designer"}],
            "support_roles": [{"id": "reality_checker"}],
            "quality_gates": {},
        }
    }

    team = ensure_video_agency_team(style_lock)
    role_ids = [role["id"] for role in team["core_roles"] + team["support_roles"]]

    assert "reality_checker" not in role_ids
    assert "style_lock_quality_reviewer" in role_ids
    assert style_lock["agency_team"] == team
```

- [ ] **Step 4: Run team tests and verify they fail before implementation**

Run:

```powershell
pytest server/tests/test_agency_orchestrator.py::test_video_agency_team_contains_current_quality_roles_without_legacy server/tests/test_agency_orchestrator.py::test_agency_context_includes_quality_role_briefs_for_stage_prompts server/tests/test_agency_orchestrator.py::test_ensure_video_agency_team_upgrades_team_containing_legacy_reality_checker -q
```

Expected: failures because `video_agency_team.py` still includes `reality_checker` and `build_agency_context()` only returns core role briefs.

- [ ] **Step 5: Update version and support roles**

In `server/app/services/video_agency_team.py`, set:

```python
VIDEO_AGENCY_TEAM_VERSION = "2026-06-02.1"
```

Replace `_SUPPORT_ROLES` with entries for `video_optimization_specialist` plus the seven QA experts:

```python
_SUPPORT_ROLES = [
    {
        "id": "video_optimization_specialist",
        "name": "Video Optimization Specialist",
        "source_role": "marketing-video-optimization-specialist",
        **_source_metadata("video_optimization_specialist"),
        "phase": _phases("video_optimization_specialist"),
        "mission": "Improve retention, chapter rhythm, title/cover packaging, and cross-platform video readiness.",
        "directives": [
            "Keep final packaging aligned with the locked delivery policy.",
            "Protect retention without breaking story clarity.",
        ],
    },
    {
        "id": "style_lock_quality_reviewer",
        "name": "Style Lock Quality Reviewer",
        "source_role": "style-lock-quality-reviewer",
        **_source_metadata("style_lock_quality_reviewer"),
        "phase": _phases("style_lock_quality_reviewer"),
        "mission": "Verify locked character, scene, visual, audio, subtitle, BGM, and missing asset rules before batch production.",
        "directives": ["Block production when locked references or executable style constraints are missing."],
    },
    {
        "id": "storyboard_quality_reviewer",
        "name": "Storyboard Quality Reviewer",
        "source_role": "storyboard-quality-reviewer",
        **_source_metadata("storyboard_quality_reviewer"),
        "phase": _phases("storyboard_quality_reviewer"),
        "mission": "Verify every storyboard frame is complete, executable, and tied to locked characters and scenes.",
        "directives": ["Block frames missing required production fields or continuity notes."],
    },
    {
        "id": "image_stage_quality_reviewer",
        "name": "Image Stage Quality Reviewer",
        "source_role": "image-stage-quality-reviewer",
        **_source_metadata("image_stage_quality_reviewer"),
        "phase": _phases("image_stage_quality_reviewer"),
        "mission": "Verify image generation requests carry locked references, identity anchors, camera, lighting, and provider constraints.",
        "directives": ["Block prompts that re-invent locked characters or scenes."],
    },
    {
        "id": "image_review_quality_reviewer",
        "name": "Image Review Quality Reviewer",
        "source_role": "image-review-quality-reviewer",
        **_source_metadata("image_review_quality_reviewer"),
        "phase": _phases("image_review_quality_reviewer"),
        "mission": "Verify generated images are stable enough to enter image-to-video production.",
        "directives": ["Block images with identity drift, locked style conflict, distortion, or unusable composition."],
    },
    {
        "id": "video_stage_quality_reviewer",
        "name": "Video Stage Quality Reviewer",
        "source_role": "video-stage-quality-reviewer",
        **_source_metadata("video_stage_quality_reviewer"),
        "phase": _phases("video_stage_quality_reviewer"),
        "mission": "Verify video generation requests have approved images, action, emotion, camera motion, duration, and continuity instructions.",
        "directives": ["Block requests that try to generate unstable long segments in one pass."],
    },
    {
        "id": "video_review_quality_reviewer",
        "name": "Video Review Quality Reviewer",
        "source_role": "video-review-quality-reviewer",
        **_source_metadata("video_review_quality_reviewer"),
        "phase": _phases("video_review_quality_reviewer"),
        "mission": "Verify video clips preserve identity, motion, camera stability, and usable transition points.",
        "directives": ["Block clips with drift, deformation, flicker, unusable motion, or missing human review."],
    },
    {
        "id": "compose_quality_reviewer",
        "name": "Compose Quality Reviewer",
        "source_role": "compose-quality-reviewer",
        **_source_metadata("compose_quality_reviewer"),
        "phase": _phases("compose_quality_reviewer"),
        "mission": "Verify final edit manifest, packaging, output video, duration, and writeback readiness.",
        "directives": ["Block asset writeback when final video, edit manifest, or review requirements are incomplete."],
    },
]
```

- [ ] **Step 6: Update `build_agency_context()` to include QA briefs**

In `server/app/services/video_agency_team.py`, replace the `role_brief` list comprehension with:

```python
        "role_brief": [
            {
                "id": role.get("id"),
                "mission": role.get("mission"),
                "directives": role.get("directives", []),
                "phase": role.get("phase", []),
            }
            for role in list(team.get("core_roles", [])) + list(team.get("support_roles", []))
            if role.get("id")
        ],
```

- [ ] **Step 7: Run team and style-lock tests**

Run:

```powershell
pytest server/tests/test_agency_orchestrator.py server/tests/test_series_style_lock_pipeline.py -q
```

Expected: tests pass after Task 1 and Task 3 are complete.

- [ ] **Step 8: Commit team version changes**

Run:

```powershell
git add server/app/services/video_agency_team.py server/tests/test_agency_orchestrator.py server/tests/test_series_style_lock_pipeline.py
git commit -m "feat: upgrade video agency team quality gates"
```

---

### Task 5: Agency Console Current Team, Historical Audit, And QA Output Fields

**Files:**

- Modify: `server/app/services/agency_console.py`
- Modify: `server/app/services/agency_contracts.py`
- Test: `server/tests/test_agency_console.py`

- [ ] **Step 1: Update pending console test expectations**

In `server/tests/test_agency_console.py`, update `test_agency_console_returns_pending_steps_without_style_lock()`:

```python
assert len(data["expert_team"]) == 14
assert "reality_checker" not in [item["expert_id"] for item in data["expert_team"]]
assert data["agency_team_status"]["core_role_count"] == 6
assert data["agency_team_status"]["support_role_count"] == 8
```

Keep the existing loop that compares `stage_graph` against `STAGE_DAG`; it will now validate the new QA assignments.

- [ ] **Step 2: Add historical reality checker display test**

Append to `server/tests/test_agency_console.py`:

```python
def test_agency_console_keeps_legacy_reality_checker_only_in_history(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    legacy = _agency_invocation(
        db,
        series.id,
        idempotency_key=f"console-{series.id}-legacy-reality",
        stage="storyboard",
        expert_id="reality_checker",
        role="qa",
        output_summary_json={"decision": "legacy decision"},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    assert "reality_checker" not in [item["expert_id"] for item in data["expert_team"]]
    assert "reality_checker" not in [item["expert_id"] for item in data["expert_invocations"]]
    for node in data["stage_graph"]:
        assert "reality_checker" not in node["reviewers"]
        assert node["lead"] != "reality_checker"
        assert "reality_checker" not in node["qa"]
    assert legacy.id in [item["id"] for item in data["decision_log"]]
    log_item = next(item for item in data["decision_log"] if item["id"] == legacy.id)
    assert log_item["legacy"] is True
    assert log_item["display_scope"] == "historical_audit"
```

- [ ] **Step 3: Add QA output field test**

Append:

```python
def test_agency_console_exposes_quality_reviewer_decision_evidence_and_next_action(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    invocation = _agency_invocation(
        db,
        series.id,
        stage="image_review",
        expert_id="image_review_quality_reviewer",
        role="qa",
        result_status="blocked",
        output_summary_json={
            "decision": "blocked",
            "findings": ["角色长相漂移"],
            "required_changes": ["重新生成角色参考图"],
            "next_action": "进入改图或重绘",
        },
        evidence_json=[{"frame_id": "shot-001", "reason": "face drift"}],
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    data = resp.json()
    item = next(row for row in data["expert_invocations"] if row["id"] == invocation.id)
    assert item["decision"] == "blocked"
    assert item["findings"] == ["角色长相漂移"]
    assert item["required_changes"] == ["重新生成角色参考图"]
    assert item["evidence"] == ["shot-001: face drift"]
    assert item["next_action"] == "进入改图或重绘"
```

The raw invocation detail route may continue returning object evidence. The agency console summary must normalize evidence to strings so the decision log never renders `[object Object]` or raw JSON braces.

- [ ] **Step 4: Add redaction test for console error payload**

Append:

```python
def test_agency_console_redacts_secret_values_from_user_facing_errors(db):
    series = Series(
        title="City Healer",
        logline="A doctor solves urban mysteries.",
        genre="drama",
        total_episodes=1,
        target_duration=60,
        mode="fully_automatic",
    )
    db.add(series)
    db.flush()
    _agency_invocation(
        db,
        series.id,
        stage="storyboard",
        expert_id="storyboard_quality_reviewer",
        role="qa",
        execution_status="failed",
        result_status="failed",
        error_code="EXPERT_MODEL_AUTH_FAILED",
        error_message="Authorization: Bearer secret-token",
        output_summary_json={"decision": "Authorization: Bearer secret-token"},
    )

    client = TestClient(app)
    resp = client.get(f"/api/series/{series.id}/agency-console")

    assert resp.status_code == 200
    text = resp.text
    assert "secret-token" not in text
    assert "Bearer" not in text
    assert "模型服务授权失败" in text or "专家审查失败" in text
```

- [ ] **Step 5: Run console tests and verify they fail before implementation**

Run:

```powershell
pytest server/tests/test_agency_console.py -q
```

Expected: failures because `expert_team` still has 8 experts, legacy records are not marked, and invocation summaries do not expose all QA output fields.

- [ ] **Step 6: Update role labels and expert team output**

In `server/app/services/agency_console.py`, update `ROLE_LABELS`:

```python
ROLE_LABELS = {
    "narrative_designer": "叙事设计师",
    "visual_storyteller": "视觉叙事师",
    "image_prompt_engineer": "图像提示词工程师",
    "prompt_engineer": "提示词工程师",
    "short_video_editing_coach": "短视频剪辑指导师",
    "douyin_strategist": "抖音策略师",
    "video_optimization_specialist": "视频优化专家",
    "style_lock_quality_reviewer": "风格锁定质量审查专家",
    "storyboard_quality_reviewer": "分镜脚本质量审查专家",
    "image_stage_quality_reviewer": "图像生成质量审查专家",
    "image_review_quality_reviewer": "图像结果质量审查专家",
    "video_stage_quality_reviewer": "视频生成质量审查专家",
    "video_review_quality_reviewer": "视频结果质量审查专家",
    "compose_quality_reviewer": "合成交付质量审查专家",
}
```

- [ ] **Step 7: Update invocation summary fields**

In `server/app/services/agency_console.py`, replace `_invocation_summary()` with a version that includes QA output fields and legacy metadata:

```python
def _redact_user_text(value: Any) -> str:
    text = _safe_text(value, 500)
    lowered = text.lower()
    if "authorization" in lowered or "bearer " in lowered or "api_key" in lowered or "api key" in lowered:
        return "模型服务授权失败，请检查模型配置。"
    return text


def _redact_user_list(value: Any, *, limit: int = 5) -> list[str]:
    if not value:
        return []
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values[:limit]:
        if isinstance(item, dict):
            frame_id = item.get("frame_id") or item.get("shot_id") or item.get("id")
            reason = item.get("reason") or item.get("summary") or item.get("message") or item.get("text")
            if frame_id and reason:
                text = f"{frame_id}: {reason}"
            elif reason:
                text = str(reason)
            else:
                text = "；".join(f"{key}: {value}" for key, value in item.items() if value)
        else:
            text = str(item)
        redacted = _redact_user_text(text)
        if redacted:
            result.append(redacted)
    return result


def _invocation_summary(row: AgencyExpertInvocation) -> dict:
    output = row.output_summary_json or {}
    is_legacy = row.expert_id == "reality_checker"
    decision = output.get("decision") or output.get("summary") or row.error_message or ""
    return {
        "id": row.id,
        "stage": row.stage,
        "expert_id": row.expert_id,
        "role": row.role,
        "execution_status": row.execution_status,
        "result_status": row.result_status,
        "summary": _redact_user_text(decision),
        "decision": _redact_user_text(output.get("decision") or decision),
        "findings": _redact_user_list(output.get("findings")),
        "required_changes": _redact_user_list(output.get("required_changes")),
        "evidence": _redact_user_list(row.evidence_json, limit=3),
        "next_action": _redact_user_text(output.get("next_action") or output.get("recommendation") or ""),
        "duration_ms": row.duration_ms,
        "error_code": row.error_code,
        "legacy": is_legacy,
        "display_scope": "historical_audit" if is_legacy else "current_team",
    }
```

- [ ] **Step 8: Split current stage graph rows from historical decision-log rows**

Do not reuse one already-filtered invocation list for both current stage UI and the decision log. The current stage graph must use only current `STAGE_DAG` assignments. The decision log must still receive historical `reality_checker` rows.

In `_current_stage_assignments()` and `_current_latest_invocations()`, keep the existing `STAGE_DAG` assignment filter. Add an explicit legacy skip inside `_current_latest_invocations()`:

```python
        if row.expert_id == "reality_checker":
            continue
```

Add a separate loader for decision-log rows:

```python
def _load_legacy_reality_checker_rows(series: Series, *, limit: int = 50) -> list[AgencyExpertInvocation]:
    db = object_session(series)
    if db is None:
        return []
    return (
        db.query(AgencyExpertInvocation)
        .filter(
            AgencyExpertInvocation.series_id == series.id,
            AgencyExpertInvocation.expert_id == "reality_checker",
        )
        .order_by(AgencyExpertInvocation.created_at.desc(), AgencyExpertInvocation.id.desc())
        .limit(limit)
        .all()
    )


def _load_decision_log_invocations(
    series: Series,
    latest_run: PipelineRun | VideoProductionRun | None,
    run_type: str | None,
) -> list[AgencyExpertInvocation]:
    rows = _load_agency_invocation_rows(series, latest_run, run_type)
    legacy_rows = _load_legacy_reality_checker_rows(series, limit=50)
    merged = {row.id: row for row in [*rows, *legacy_rows]}
    return sorted(merged.values(), key=lambda row: (row.created_at, row.id))
```

Refactor the existing `_load_agency_invocations()` into an unfiltered row loader plus current filter:

```python
raw_invocations = _load_agency_invocation_rows(series, latest_run, run_type)
current_invocations = _current_latest_invocations(raw_invocations)
decision_log_invocations = _load_decision_log_invocations(series, latest_run, run_type)
stage_graph = _stage_graph(current_invocations)
expert_invocations = [_invocation_summary(row) for row in current_invocations]
decision_log = _decision_log(decision_log_invocations)
```

In `_decision_log()`, do not skip legacy records. Ensure each log item includes `id` and `invocation_id` so old and new frontend keys both work:

```python
"id": row.id,
"invocation_id": row.id,
"legacy": row.expert_id == "reality_checker",
"display_scope": "historical_audit" if row.expert_id == "reality_checker" else "current_team",
```

Update `test_agency_console_keeps_legacy_reality_checker_only_in_history()` to assert `reality_checker` is absent from `expert_invocations` and present only in `decision_log`.

- [ ] **Step 9: Run console tests**

Run:

```powershell
pytest server/tests/test_agency_console.py -q
```

Expected: all tests in `server/tests/test_agency_console.py` pass after dependent backend tasks are complete.

- [ ] **Step 10: Commit console changes**

Run:

```powershell
git add server/app/services/agency_console.py server/app/services/agency_contracts.py server/tests/test_agency_console.py
git commit -m "feat: split current agency team from historical audit"
```

---

### Task 6: Shared Frontend Expert Labels

**Files:**

- Create: `web/src/components/agency/agencyExpertLabels.js`
- Modify: `web/src/components/agency/AgencyInvocationGraph.vue`
- Modify: `web/src/components/agency/AgencyTeamMap2D.vue`
- Modify: `web/src/components/agency/AgencyTeamMap3D.vue`
- Modify: `web/src/components/agency/AgencyExpertDrawer.vue`
- Modify: `web/src/components/agency/AgencyDecisionLog.vue`
- Test: `web/src/__tests__/agency-console-page.test.js`
- Test: `web/src/__tests__/agency-3d-fallback.test.js`
- Test: `web/src/__tests__/agency-expert-drawer.test.js`

- [ ] **Step 1: Add shared label module**

Create `web/src/components/agency/agencyExpertLabels.js`:

```javascript
export const EXPERT_NAMES = {
  narrative_designer: '叙事设计师',
  visual_storyteller: '视觉叙事师',
  image_prompt_engineer: '图像提示词工程师',
  prompt_engineer: '提示词工程师',
  short_video_editing_coach: '短视频剪辑指导师',
  douyin_strategist: '抖音策略师',
  video_optimization_specialist: '视频优化专家',
  style_lock_quality_reviewer: '风格锁定质量审查专家',
  storyboard_quality_reviewer: '分镜脚本质量审查专家',
  image_stage_quality_reviewer: '图像生成质量审查专家',
  image_review_quality_reviewer: '图像结果质量审查专家',
  video_stage_quality_reviewer: '视频生成质量审查专家',
  video_review_quality_reviewer: '视频结果质量审查专家',
  compose_quality_reviewer: '合成交付质量审查专家',
  reality_checker: '历史审计角色',
}

export const EXPERT_AVATARS = {
  narrative_designer: '叙',
  visual_storyteller: '视',
  image_prompt_engineer: '图',
  prompt_engineer: '词',
  short_video_editing_coach: '剪',
  douyin_strategist: '抖',
  video_optimization_specialist: '优',
  style_lock_quality_reviewer: '锁',
  storyboard_quality_reviewer: '镜',
  image_stage_quality_reviewer: '生',
  image_review_quality_reviewer: '审',
  video_stage_quality_reviewer: '影',
  video_review_quality_reviewer: '检',
  compose_quality_reviewer: '交',
  reality_checker: '史',
}

export const PHASE_LABELS = {
  style_lock: '风格锁定',
  storyboard: '分镜脚本',
  image_stage: '图像生成',
  image_review: '图像审查',
  video_stage: '视频生成',
  video_review: '视频审查',
  compose: '合成交付',
  render: '画面生成',
  final_edit: '最终剪辑',
}

export const ROLE_LABELS = {
  core: '核心专家',
  core_expert: '核心专家',
  primary: '核心专家',
  lead: '负责人',
  leader: '负责人',
  owner: '负责人',
  responsible: '负责人',
  reviewer: '复审专家',
  reviewers: '复审专家',
  review: '复审专家',
  qa: '质量审查专家',
  quality: '质量审查专家',
  quality_assurance: '质量审查专家',
  quality_gate: '质量审查专家',
  legacy: '历史审计角色',
}

export const SKILL_TEXT = {
  narrative_designer: '负责叙事结构、角色动机、情绪推进和跨镜头故事连续性。',
  visual_storyteller: '负责视觉叙事、镜头语言、场景氛围和锁定风格一致性。',
  image_prompt_engineer: '负责文生图提示词、角色锚定图和视觉参考图组织。',
  prompt_engineer: '负责把故事意图拆解为稳定提示词，控制角色、场景和风格一致性。',
  short_video_editing_coach: '负责镜头节奏、时长拆分、剪辑包装和多镜头叙事连贯性。',
  douyin_strategist: '负责平台节奏、开场钩子、完播率判断和内容传播策略。',
  video_optimization_specialist: '负责完播率、章节节奏、封面标题和视频投放优化。',
  style_lock_quality_reviewer: '审查角色、场景、视觉、声音和包装是否足以支撑批量生产。',
  storyboard_quality_reviewer: '审查每个分镜是否字段完整、可执行，并继承锁定角色和场景。',
  image_stage_quality_reviewer: '审查图像生成请求是否携带参考图、身份锚点、镜头和光影约束。',
  image_review_quality_reviewer: '审查图片结果是否存在角色漂移、风格冲突、畸变或不可用构图。',
  video_stage_quality_reviewer: '审查视频生成请求是否具备首尾帧、动作、镜头和连续性说明。',
  video_review_quality_reviewer: '审查视频片段是否保持身份、动作、镜头稳定和可衔接结尾。',
  compose_quality_reviewer: '审查最终合成、字幕、BGM、输出规格、成片 URL 和资产写回条件。',
  reality_checker: '历史审计记录，不参与当前编排。',
}

export function expertName(id, fallback = '未命名专家') {
  return EXPERT_NAMES[id] || fallback
}

export function expertAvatar(id) {
  return EXPERT_AVATARS[id] || '专'
}

export function phaseText(phases = []) {
  const labels = phases.map(phase => PHASE_LABELS[phase] || '未命名阶段')
  return labels.length ? labels.join(' / ') : '待配置阶段'
}

export function skillText(expert = {}) {
  return SKILL_TEXT[expert.expert_id] || '负责阶段判断、内容审查与生产交接。'
}

export function roleLabel(key) {
  return ROLE_LABELS[String(key || '').trim().toLowerCase()] || ''
}
```

- [ ] **Step 2: Replace local name maps in frontend components**

In `AgencyInvocationGraph.vue`, `AgencyTeamMap2D.vue`, `AgencyTeamMap3D.vue`, `AgencyExpertDrawer.vue`, and `AgencyDecisionLog.vue`, import shared helpers:

```javascript
import { expertAvatar, expertName, phaseText, roleLabel, skillText } from './agencyExpertLabels.js'
```

For `AgencyExpertDrawer.vue`, the relative import is:

```javascript
import { expertName } from './agencyExpertLabels.js'
```

Remove local `FALLBACK_NAMES`, `NAME`, `AVATAR`, `PHASE`, `ROLE`, and `SKILL_TEXT` constants from those components after the imports are wired.

- [ ] **Step 3: Update role label normalization in `AgencyTeamMap3D.vue`**

In `AgencyTeamMap3D.vue`, replace `normalizeRoleLabels()` with:

```javascript
function normalizeRoleLabels(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.flatMap(normalizeRoleLabels)
  if (typeof value === 'object') {
    return normalizeRoleLabels(value.role_type || value.role || value.type)
  }
  const label = roleLabel(value)
  return label ? [label] : []
}
```

- [ ] **Step 4: Run frontend tests and verify failures identify old maps**

Run:

```powershell
cd web
npm test -- agency-console-page agency-3d-fallback agency-expert-drawer
```

Expected before component imports are fully replaced: tests may fail with missing constants or old `现实检验者` expectations.

- [ ] **Step 5: Commit shared labels**

Run:

```powershell
git add web/src/components/agency/agencyExpertLabels.js web/src/components/agency/AgencyInvocationGraph.vue web/src/components/agency/AgencyTeamMap2D.vue web/src/components/agency/AgencyTeamMap3D.vue web/src/components/agency/AgencyExpertDrawer.vue web/src/components/agency/AgencyDecisionLog.vue
git commit -m "feat: share agency expert frontend labels"
```

---

### Task 7: Frontend Current Team, Legacy Drawer, And QA Output Rendering

**Files:**

- Modify: `web/src/components/agency/AgencyExpertDrawer.vue`
- Modify: `web/src/components/agency/AgencyDecisionLog.vue`
- Modify: `web/src/components/agency/AgencyInvocationGraph.vue`
- Modify: `web/src/views/AgencyConsolePage.vue`
- Test: `web/src/__tests__/agency-console-page.test.js`
- Test: `web/src/__tests__/agency-expert-drawer.test.js`

- [ ] **Step 1: Update agency console page mock to 14 current experts**

In `web/src/__tests__/agency-console-page.test.js`, replace the mocked `expert_team` with:

```javascript
expert_team: [
  { expert_id: 'narrative_designer', name: '叙事设计师', phases: ['storyboard'] },
  { expert_id: 'visual_storyteller', name: '视觉叙事师', phases: ['style_lock', 'image_review'] },
  { expert_id: 'image_prompt_engineer', name: '图像提示词工程师', phases: ['style_lock', 'image_stage'] },
  { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['image_stage', 'video_stage'] },
  { expert_id: 'short_video_editing_coach', name: '短视频剪辑指导师', phases: ['style_lock', 'storyboard', 'video_stage', 'compose'] },
  { expert_id: 'douyin_strategist', name: '抖音策略师', phases: ['storyboard', 'compose'] },
  { expert_id: 'video_optimization_specialist', name: '视频优化专家', phases: ['video_review', 'compose'] },
  { expert_id: 'style_lock_quality_reviewer', name: '风格锁定质量审查专家', role_type: 'quality', phases: ['style_lock'] },
  { expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', role_type: 'quality', phases: ['storyboard'] },
  { expert_id: 'image_stage_quality_reviewer', name: '图像生成质量审查专家', role_type: 'quality', phases: ['image_stage'] },
  { expert_id: 'image_review_quality_reviewer', name: '图像结果质量审查专家', role_type: 'quality', phases: ['image_review'] },
  { expert_id: 'video_stage_quality_reviewer', name: '视频生成质量审查专家', role_type: 'quality', phases: ['video_stage'] },
  { expert_id: 'video_review_quality_reviewer', name: '视频结果质量审查专家', role_type: 'quality', phases: ['video_review'] },
  { expert_id: 'compose_quality_reviewer', name: '合成交付质量审查专家', role_type: 'quality', phases: ['compose'] },
],
```

Update the mocked `stage_graph` quality fields to use stage-specific QA ids.

- [ ] **Step 2: Add console test for no current legacy role**

Append in `web/src/__tests__/agency-console-page.test.js`:

```javascript
it('does not show the legacy reality checker in the current team or stage graph', async () => {
  const wrapper = mount(AgencyConsolePage)
  await flushPromises()

  expect(wrapper.text()).toContain('风格锁定质量审查专家')
  expect(wrapper.text()).toContain('分镜脚本质量审查专家')
  expect(wrapper.text()).toContain('14 位当前专家')
  expect(wrapper.text()).toContain('7 个阶段质量门')
  expect(wrapper.text()).not.toContain('8 位视频专家')
  expect(wrapper.text()).not.toContain('现实检验者')
})
```

Then update `AgencyConsolePage.vue` command metrics so the first-screen copy matches the new team topology. The expert-team metric must be derived from the current team payload when available and must mention `14 位当前专家` plus `7 个阶段质量门` in the fallback copy. Do not leave any visible text that says the current team has 8 experts.

- [ ] **Step 3: Add drawer test for legacy expert badge**

Append to `web/src/__tests__/agency-expert-drawer.test.js`:

```javascript
it('shows legacy audit badge for old reality checker detail', async () => {
  getAgencyExpert.mockResolvedValueOnce({
    data: {
      expert_id: 'reality_checker',
      name: '历史审计角色',
      role_type: 'legacy',
      legacy: true,
      source_path: 'testing/testing-reality-checker.md',
      source_commit: 'legacy',
      sha256: '',
      markdown: '# 历史审计角色\n\n这是历史审计记录，不参与当前编排。',
    },
  })

  const wrapper = mount(AgencyExpertDrawer, {
    props: { expertId: 'reality_checker' },
  })
  await flushPromises()

  expect(wrapper.text()).toContain('历史审计角色')
  expect(wrapper.text()).toContain('历史审计记录')
  expect(wrapper.text()).toContain('不参与当前编排')
})
```

- [ ] **Step 4: Update drawer markup for legacy badge**

In `AgencyExpertDrawer.vue`, inside the title block after the `<h2>`, add:

```vue
<div v-if="expert?.legacy" class="mt-2 inline-flex rounded border border-amber-300/40 bg-amber-300/10 px-2 py-1 text-xs text-amber-100">
  历史审计记录，不参与当前编排
</div>
```

- [ ] **Step 5: Render QA output fields in decision log**

In `AgencyDecisionLog.vue`, replace the table-only presentation with a responsive review log. Desktop can keep table columns for scan speed, but each item must expose a stacked detail block; mobile must not require horizontal scrolling to understand the QA result. Render these fields when present:

```vue
<div v-if="item.legacy" class="mt-2 inline-flex rounded border border-amber-300/40 bg-amber-300/10 px-2 py-1 text-xs text-amber-100">
  历史审计记录
</div>
<div class="mt-2 flex flex-wrap gap-2 text-xs">
  <span class="rounded border border-zinc-700 px-2 py-1 text-zinc-300">{{ phaseText(item.stage) }}</span>
  <span class="rounded border border-zinc-700 px-2 py-1 text-zinc-300">{{ expertName(item.expert_id) }}</span>
  <span v-if="item.display_scope === 'historical_audit'" class="rounded border border-amber-300/40 bg-amber-300/10 px-2 py-1 text-amber-100">历史记录</span>
</div>
<div v-if="item.findings?.length" class="mt-2 text-xs leading-5 text-zinc-300">
  <span class="text-zinc-500">发现：</span>{{ item.findings.join('；') }}
</div>
<div v-if="item.required_changes?.length" class="mt-1 text-xs leading-5 text-zinc-300">
  <span class="text-zinc-500">必须修改：</span>{{ item.required_changes.join('；') }}
</div>
<div v-if="item.evidence?.length" class="mt-1 text-xs leading-5 text-zinc-300">
  <span class="text-zinc-500">证据：</span>{{ item.evidence.slice(0, 3).join('；') }}
</div>
<div v-if="item.next_action" class="mt-1 text-xs leading-5 text-cyan-100">
  <span class="text-zinc-500">下一步：</span>{{ item.next_action }}
</div>
```

Add filter chips above the log: `全部`, `当前审查`, and `历史审计`. `当前审查` filters `display_scope === 'current_team' && !item.legacy`; `历史审计` filters `display_scope === 'historical_audit' || item.legacy`. The default remains `全部` so existing history is not hidden.

Append a frontend test that mounts the decision log with one current QA record and one legacy `reality_checker` record, then asserts:

```javascript
expect(wrapper.text()).toContain('当前审查')
expect(wrapper.text()).toContain('历史审计')
expect(wrapper.text()).toContain('发现：')
expect(wrapper.text()).toContain('必须修改：')
expect(wrapper.text()).toContain('证据：')
expect(wrapper.text()).toContain('下一步：')
expect(wrapper.text()).not.toContain('{')
```

- [ ] **Step 6: Ensure invocation graph uses current stage QA only**

In `AgencyInvocationGraph.vue`, do not derive QA from `decision_log`. Keep using `stage.qa || []` for quality gate buttons. Add a fallback empty state inside the QA section:

```vue
<span v-if="!(stage.qa || []).length" class="text-zinc-600">暂无质量审查专家</span>
```

- [ ] **Step 7: Run frontend console and drawer tests**

Run:

```powershell
cd web
npm test -- agency-console-page agency-expert-drawer
```

Expected: tests pass after Task 6 is complete.

- [ ] **Step 8: Commit frontend current/historical split**

Run:

```powershell
git add web/src/components/agency/AgencyExpertDrawer.vue web/src/components/agency/AgencyDecisionLog.vue web/src/components/agency/AgencyInvocationGraph.vue web/src/views/AgencyConsolePage.vue web/src/__tests__/agency-console-page.test.js web/src/__tests__/agency-expert-drawer.test.js
git commit -m "feat: show agency quality gates and legacy audit records"
```

---

### Task 8: 2D And 3D Expert Maps With 14 Current Experts

**Files:**

- Modify: `web/src/components/agency/AgencyTeamMap2D.vue`
- Modify: `web/src/components/agency/AgencyTeamMap3D.vue`
- Test: `web/src/__tests__/agency-3d-fallback.test.js`
- Test: `web/src/__tests__/agency-control-room.test.js`

- [ ] **Step 1: Update 3D fallback tests to current QA experts**

In `web/src/__tests__/agency-3d-fallback.test.js`, replace test experts containing `reality_checker` with:

```javascript
{ expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', phases: ['storyboard'], role_type: 'quality' }
```

Update matching `stageGraph` entries:

```javascript
qa: ['storyboard_quality_reviewer'],
```

- [ ] **Step 2: Add 14-expert fallback test**

Append to `web/src/__tests__/agency-3d-fallback.test.js`:

```javascript
it('renders all fourteen current experts without showing the legacy reality checker', () => {
  const currentExperts = [
    'narrative_designer',
    'visual_storyteller',
    'image_prompt_engineer',
    'prompt_engineer',
    'short_video_editing_coach',
    'douyin_strategist',
    'video_optimization_specialist',
    'style_lock_quality_reviewer',
    'storyboard_quality_reviewer',
    'image_stage_quality_reviewer',
    'image_review_quality_reviewer',
    'video_stage_quality_reviewer',
    'video_review_quality_reviewer',
    'compose_quality_reviewer',
  ].map(expert_id => ({ expert_id, name: expertName(expert_id), phases: ['storyboard'], role_type: expert_id.includes('quality') ? 'quality' : 'core' }))

  const wrapper = mountComponent({
    props: {
      experts: currentExperts,
      stageGraph: [{
        stage: 'storyboard',
        status: 'running',
        lead: 'narrative_designer',
        reviewers: ['visual_storyteller'],
        qa: ['storyboard_quality_reviewer'],
      }],
      invocations: [],
      webglAvailable: false,
    },
  })

  expect(wrapper.findAll('[data-expert-id]')).toHaveLength(14)
  expect(wrapper.text()).toContain('分镜脚本质量审查专家')
  expect(wrapper.text()).not.toContain('现实检验者')
})
```

Add import near the top:

```javascript
import { expertName } from '../components/agency/agencyExpertLabels.js'
```

- [ ] **Step 3: Add active QA highlight test**

Append:

```javascript
it('activates only the current stage quality reviewer in 3D mode', async () => {
  useWebgl()
  const wrapper = mountComponent({
    props: {
      experts: [
        { expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家', phases: ['storyboard'], role_type: 'quality' },
        { expert_id: 'video_review_quality_reviewer', name: '视频结果质量审查专家', phases: ['video_review'], role_type: 'quality' },
      ],
      stageGraph: [{
        stage: 'storyboard',
        status: 'running',
        lead: 'narrative_designer',
        reviewers: [],
        qa: ['storyboard_quality_reviewer'],
      }],
      invocations: [],
      webglAvailable: true,
    },
  })
  await flushPromises()

  expect(latestAvatarTitle('storyboard_quality_reviewer')?.userData.active).toBe(true)
  expect(latestAvatarTitle('video_review_quality_reviewer')?.userData.active).toBe(false)
})
```

- [ ] **Step 4: Ensure 2D map groups current experts and no longer says 8 experts**

In `AgencyTeamMap2D.vue`, group experts by current business role before rendering seats:

- `core`: 核心创作
- `quality`: 阶段质检
- `support`: 优化支持
- `legacy`: render only inside historical drawers/logs, never inside the current map

Each group needs a small section label and count, for example `阶段质检 · 7`. This prevents the 14-expert map from becoming an unreadable list of equal-weight avatars.

Replace the subtitle with current-team copy:

```vue
<p class="mt-1 text-xs leading-5 text-zinc-500">14 位当前视频专家按阶段接力，质量审查专家只在对应阶段亮起。</p>
```

Add tests that assert the visible group labels exist and that no visible current-map copy contains `8 位视频专家`.

- [ ] **Step 5: Ensure 3D role props treat quality reviewers distinctly**

In `AgencyTeamMap3D.vue`, update `addAvatarProp()` so quality experts use a quality visual prop instead of the old `reality_checker` branch. Replace the branch:

```javascript
if (expertId === 'video_optimization_specialist' || expertId === 'reality_checker') {
```

with:

```javascript
if (expertId === 'video_optimization_specialist' || expertId.endsWith('_quality_reviewer')) {
```

Also add a small legend overlay that explains the current 3D semantics in Chinese:

- `亮起`: 当前阶段正在参与
- `待命`: 当前阶段不参与，但属于当前专家团队
- `历史`: 不在 3D 当前团队中展示

The 3D view is decorative support for transparency, so do not hide the 2D grouped map or decision log behind it.

- [ ] **Step 6: Run map tests**

Run:

```powershell
cd web
npm test -- agency-3d-fallback agency-control-room
```

Expected: tests pass after Task 6 is complete.

- [ ] **Step 7: Commit map updates**

Run:

```powershell
git add web/src/components/agency/AgencyTeamMap2D.vue web/src/components/agency/AgencyTeamMap3D.vue web/src/__tests__/agency-3d-fallback.test.js web/src/__tests__/agency-control-room.test.js
git commit -m "feat: render current quality experts in agency maps"
```

---

### Task 9: End-To-End Verification And Plan Closure

**Files:**

- Modify only if tests reveal a direct miss in files already covered by Tasks 1-8.

- [ ] **Step 1: Run backend expert contract tests**

Run:

```powershell
pytest server/tests/test_agency_manifest.py server/tests/test_agency_api.py server/tests/test_agency_orchestrator.py server/tests/test_agency_console.py server/tests/test_series_style_lock_pipeline.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 2: Run frontend agency tests**

Run:

```powershell
cd web
npm test -- agency-api agency-console-page agency-control-room agency-3d-fallback agency-expert-drawer
```

Expected: all selected frontend tests pass.

- [ ] **Step 3: Run a focused grep for forbidden current-team legacy references**

Run:

```powershell
rg -n "reality_checker|现实检验者" server/app web/src
```

Expected allowed occurrences:

- `server/app/services/agency_manifest.py` legacy constants and helpers.
- `server/app/routers/agency.py` legacy detail handling.
- `server/app/services/agency_console.py` historical audit handling.
- `web/src/components/agency/agencyExpertLabels.js` legacy fallback label.
- `web/src/components/agency/AgencyDecisionLog.vue` historical display path.

Any occurrence inside current `STAGE_DAG`, current `EXPERT_IDS`, current `build_video_agency_team()` roles, current `expert_team` mocks, or current stage graph mocks must be removed.

- [ ] **Step 4: Run manifest verification command**

Run:

```powershell
pytest server/tests/test_agency_manifest.py::test_manifest_hashes_match_vendored_markdown -q
```

Expected: pass with `checked_count == 14`.

- [ ] **Step 5: Save final implementation evidence**

Create or update an implementation report only if the execution session wants a report artifact:

```powershell
New-Item -ItemType Directory -Path docs/superpowers/reports -Force
```

Use this exact filename if a report is created:

```text
docs/superpowers/reports/2026-06-02-stage-quality-review-experts-implementation-report.md
```

Include the verification commands and pass/fail results. Do not include API keys or provider payloads.

- [ ] **Step 6: Commit final verification report if created**

Run only if the report file exists:

```powershell
git add docs/superpowers/reports/2026-06-02-stage-quality-review-experts-implementation-report.md
git commit -m "docs: record stage quality reviewer verification"
```

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run in this pass | Not required for this narrow expert-contract correction. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not run | No code diff was reviewed in this plan pass. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 4 issues found and fixed in the plan: display scope mismatch, current/history row coupling, evidence object rendering, and missing typed response contract. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR | Score moved from 7-8/10 areas to 9/10 after responsive QA log, grouped maps, and dynamic metrics were added. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | Not needed for this implementation plan. |

- **UNRESOLVED:** 0 after this engineering review.
- **VERDICT:** ENG + DESIGN CLEARED. Ready to implement with the revised contract.

---

## Engineering Review Addendum

### Scores

- Architecture fit: 9/10. The plan keeps the embedded expert-team model and avoids a new registry or database table.
- Data contract safety: 9/10 after adding typed `AgencyInvocationSummary`, `AgencyDecisionLogItem`, and canonical `display_scope` values.
- Historical compatibility: 9/10 after splitting current-stage rows from historical decision-log rows.
- Testability: 8/10. Focused backend and frontend tests are specified, but implementation should still run the final grouped test command before claiming completion.
- Operational risk: 8/10. Manifest/hash validation remains strict; implementation must avoid repeated blocker traces by validating manifest once before current stage invocation creation.

### Issues Fixed In This Plan

- `display_scope` was inconsistent between backend and frontend. The plan now uses only `current_team` and `historical_audit`.
- Historical `reality_checker` rows could have been filtered out before `decision_log` rendering. The plan now requires separate current and decision-log loaders.
- `evidence` was object-shaped in backend tests but rendered with `join()` in the frontend. The console summary contract now requires `evidence: list[str]`.
- The response contract was under-typed. The plan now adds `AgencyDecisionLogItem` and extends `AgencyInvocationSummary` with QA output fields.

### Engineering Gates

- Do not start frontend implementation until backend tests prove `expert_invocations` excludes `reality_checker` while `decision_log` still includes historical records.
- Do not render raw evidence objects in the agency console. Raw evidence belongs in invocation detail, not the visible decision log.
- Do not add a new table, dynamic expert registry, or expert management UI in this phase.
- Do not mark implementation complete until backend agency tests and frontend agency console/map tests both pass.

---

## Design Review Addendum

### Scores

- Information architecture: 8/10 -> 9/10 after adding current/historical filters, grouped maps, and dynamic console metrics.
- Process transparency: 8/10 -> 9/10 after making QA findings, required changes, evidence, and next action first-class review sections.
- Visual clarity: 7/10 -> 9/10 after requiring 2D role grouping and 3D active/standby/legacy legend semantics.
- Implementation risk: 8/10. The plan remains scoped to existing agency console components and API response fields, with no new database table or provider protocol.

### Required Design Decisions

- The agency console must not present quality review as a hidden backend event. Every stage QA record needs readable Chinese sections for `发现`, `必须修改`, `证据`, and `下一步`.
- Historical `reality_checker` records are valid audit history, not current participants. They must be visually marked as historical and filtered separately from current review work.
- The first-screen console metrics must match the current manifest. The UI cannot keep stale `8 位视频专家` copy after the 14-expert topology ships.
- The 2D expert map is the primary readable team map. The 3D room remains a visual transparency layer and must not be the only way to understand responsibility or stage progress.
- Inactive current experts should appear as standby, not failed, skipped, or hidden. Legacy experts should not appear in current 2D/3D maps.

---

## Self-Review

### Spec Coverage

- Current 14-expert manifest and removal of active `reality_checker`: Tasks 1, 3, 4, 5, 8, 9.
- Seven stage-specific QA markdown files: Task 1.
- Each stage exactly one QA expert: Task 3.
- Legacy read-only `reality_checker`: Tasks 1, 2, 5, 7.
- Manifest/hash configuration blocker: Tasks 1, 2, 5, 9.
- Redacted user-facing errors: Tasks 2, 3, 5, 7.
- `VIDEO_AGENCY_TEAM_VERSION` upgrade and old series team replacement: Task 4.
- `build_agency_context()` includes QA briefs: Task 4.
- Frontend source split and shared fallback labels: Tasks 6, 7, 8.
- QA output fields rendered in Chinese: Tasks 5 and 7.
- Tests for current no old expert plus historical compatibility: Tasks 1-9.

### Placeholder Scan

This plan intentionally contains no deferred implementation placeholders. The `<computed hash>` marker appears only inside an instruction block for manifest editing and is paired with the exact command that produces the required value before saving.

### Type Consistency

- Current expert payload uses `expert_id`, `name`, `role_type`, `source_path`, `source_commit`, `sha256`, `phases`, and optional `legacy`.
- Invocation summaries use `decision`, `findings`, `required_changes`, `evidence`, `next_action`, `legacy`, and `display_scope`.
- Frontend helpers use `expertName`, `expertAvatar`, `phaseText`, `roleLabel`, and `skillText`.
- Stage QA ids match the confirmed V2 contract exactly.
