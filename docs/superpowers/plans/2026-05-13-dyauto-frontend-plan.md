# dy_auto 前端 — AI 视频工坊 + 系列管理 UI 实施计划 (Plan C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans.

**Goal:** 在 dy_auto 管理后台实现完整的系列短剧管理 UI，包括角色/场景资产库、AI 模型配置中心、七层流水线监控面板、全透明可观测性看板。

**Architecture:** Vue 3 + Element Plus + Tailwind CSS。新增 6 个页面 + ~8 个组件。所有 API 通过 api/*.js 客户端层调用 Plan B 后端。渲染参数通过 Pixelle proxy 传递。

**Tech Stack:** Vue 3 (Composition API), Pinia, Vue Router 4, Element Plus, Tailwind CSS, Axios

**前置:** Plan A (Pixelle-Video) + Plan B (dy_auto backend) 已完成

---

### Task 1: API 客户端层

**Files:**
- Create: `web/src/api/series.js`
- Create: `web/src/api/characters.js`
- Create: `web/src/api/scenes.js`
- Create: `web/src/api/pipeline.js`
- Create: `web/src/api/aiConfig.js`

遵循现有 `web/src/api/*.js` 模式 (import client → export functions)。

- [ ] **Step 1: 创建 5 个 API 模块**

```js
// web/src/api/series.js
import client from './client.js'

export function listSeries(params) { return client.get('/series', { params }) }
export function createSeries(data) { return client.post('/series', data) }
export function getSeries(id) { return client.get(`/series/${id}`) }
export function updateSeries(id, data) { return client.put(`/series/${id}`, data) }
export function linkCharacter(seriesId, characterId) { return client.post(`/series/${seriesId}/characters/${characterId}`) }
export function linkScene(seriesId, sceneId) { return client.post(`/series/${seriesId}/scenes/${sceneId}`) }
export function updateEpisode(seriesId, episodeId, data) { return client.put(`/series/${seriesId}/episodes/${episodeId}`, data) }
```

```js
// web/src/api/characters.js
import client from './client.js'

export function listCharacters() { return client.get('/characters') }
export function createCharacter(data) { return client.post('/characters', data) }
export function updateCharacter(id, data) { return client.put(`/characters/${id}`, data) }
export function deleteCharacter(id) { return client.delete(`/characters/${id}`) }
```

```js
// web/src/api/pipeline.js
import client from './client.js'

export function startPipeline(seriesId, episodeId, mode) { return client.post('/pipeline/start', null, { params: { series_id: seriesId, episode_id: episodeId, mode } }) }
export function resumePipeline(runId) { return client.post(`/pipeline/resume/${runId}`) }
export function listRuns(seriesId) { return client.get(`/pipeline/runs/${seriesId}`) }
```

```js
// web/src/api/aiConfig.js
import client from './client.js'

export function getModels() { return client.get('/ai-config/models') }
export function updateModels(data) { return client.put('/ai-config/models', data) }
```

- [ ] **Step 2: Commit**

---

### Task 2: AI 模型配置中心页面

**Files:**
- Create: `web/src/views/AIConfigPage.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue` — 菜单入口

对标 Pixelle-Video 的 Streamlit 系统配置面板，提供所有 AI 模型的集中配置 UI。

**页面结构：**

```
┌─────────────────────────────────────────────────────────────┐
│  AI 模型配置中心                                              │
├─────────────────────────────────────────────────────────────┤
│  LLM 模型         │  API Key    │  Base URL   │  Model      │
│  ─────────────────│─────────────│─────────────│─────────────│
│  DeepSeek  ○      │  ****a1b2  │ api.ds.com  │ ds-chat     │
│  GPT-4o    ○      │  ****c3d4  │ api.oai.com │ gpt-4o      │
│                                                             │
│  视频模型          │  Provider   │  API Key    │  状态       │
│  ─────────────────│─────────────│─────────────│─────────────│
│  Seedance 2.0     │  volcengine │  ****xxxx   │  ✓ 已启用    │
│  Kling 3.0        │  kuaishou   │  ****yyyy   │  ✓ 已启用    │
│  Wan 2.7          │  runninghub │  —          │  ✓ 已启用    │
│                                                             │
│  OSS 存储         │  Provider   │  Endpoint   │  Bucket     │
│  ─────────────────│─────────────│─────────────│─────────────│
│  MinIO (本地)     │  minio      │  loc:9000   │  dy-auto    │
│                                                             │
│  [测试连通性] [保存全部配置]                                    │
└─────────────────────────────────────────────────────────────┘
```

实现要点：
- `reactive()` 管理所有配置字段
- 敏感字段 (API Key) 使用 `type="password"` + 可切换显示
- Provider quick-select 按钮自动填充 Base URL 和 Model
- 「测试连通性」按钮发 `/api/ai-config/test` 验证每个模型
- 配置保存到 localStorage 作为 local cache

- [ ] **Step 1: 创建 AIConfigPage.vue (~250 行)**

- [ ] **Step 2: 添加路由**

```js
// router/index.js
{ path: 'ai-config', name: 'AIConfig', component: () => import('../views/AIConfigPage.vue') }
```

- [ ] **Step 3: 侧边栏菜单添加「AI 模型配置」入口**

- [ ] **Step 4: Commit**

---

### Task 3: 角色资产库页面

**Files:**
- Create: `web/src/views/CharactersPage.vue`
- Create: `web/src/components/character/CharacterCard.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue` — 菜单

角色 CRUD + 参考图管理。网格卡片布局。

**页面结构：**

```
┌─────────────────────────────────────────────────────────────┐
│  角色资产库                                    [+ 新建角色]  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ 正面照   │ │ 侧面照   │ │ 正面照   │ │ 侧面照   │      │
│  │          │ │          │ │          │ │          │      │
│  │ 高冷总裁 │ │ 活泼实习生│ │ 温柔闺蜜 │ │ 刻薄上司 │      │
│  │ 男主     │ │ 女主     │ │ 女配     │ │ 反派     │      │
│  │ ✓ 图已就绪│ │ ⏳ 待生成 │ │ ✓ 图已就绪│ │ ✓ 图已就绪│      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  [生成角色图] — 调 Pixelle API → FLUX → OSS → 写入DB → 刷新  │
└─────────────────────────────────────────────────────────────┘
```

实现要点：
- CharacterCard 展示角色名 + 正面照缩略图 + 角色类型 badge + 参考图就绪状态
- 新建角色：Dialog 表单 (name/role_type/gender/personality/appearance_desc/outfit_desc)
- 「生成角色图」按钮调用 Pixelle API 触发 FLUX 生成 + OSS 上传

- [ ] **Step 1: 创建 ~200 行**

- [ ] **Step 2: 添加路由 + 菜单**

- [ ] **Step 3: Commit**

---

### Task 4: 系列管理页面

**Files:**
- Create: `web/src/views/SeriesListPage.vue`
- Create: `web/src/views/SeriesDetailPage.vue`
- Create: `web/src/components/series/EpisodeList.vue`
- Modify: `web/src/router/index.js`
- Modify: `web/src/views/AdminLayout.vue` — 菜单

系列列表 + 详情（剧集管理 + 角色/场景关联）。

**页面结构：**

```
┌─────────────────────────────────────────────────────────────┐
│  系列管理                                                    │
├─────────────────────────────────────────────────────────────┤
│  [新建系列]  [模式: 逐步确认 ▼]                               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 都市爱情故事          30 集  |  90s/集  |  渲染中      │    │
│  │ 进度: ████████░░ 70%  |  E21/30 完成                 │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 古装悬疑探案          30 集  |  120s/集 |  剧本已生成  │    │
│  │ 进度: ██░░░░░░░░ 20%  |  E1 pilot 渲染完成           │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

SeriesDetailPage (点击系列进入):

```
┌─────────────────────────────────────────────────────────────┐
│  都市爱情故事 — 系列详情                                     │
├─────────────────────────────────────────────────────────────┤
│  [角色: 3] [场景: 5]  [故事圣经] [流水线监控]                │
│                                                             │
│  剧集列表:                                                   │
│  E01 ✓ 初遇咖啡馆  | 95s  | done     | [预览]              │
│  E02 ✓ 误会开始    | 92s  | done     | [预览]              │
│  E03 ⏳ 夜雨告白   | —    | rendering| —                  │
│  E04 ⏹ 冷战爆发   | —    | pending  | —                  │
│  ...                                                        │
│                                                             │
│  [从 E03 恢复]  [一键生成全部]  [Pilot预览后批量]            │
└─────────────────────────────────────────────────────────────┘
```

- [ ] **Step 1: SeriesListPage (~180 行)**

- [ ] **Step 2: SeriesDetailPage + EpisodeList (~250 行)**

- [ ] **Step 3: 添加路由**

```js
{ path: 'series', name: 'SeriesList', component: () => import('../views/SeriesListPage.vue') },
{ path: 'series/:id', name: 'SeriesDetail', component: () => import('../views/SeriesDetailPage.vue') },
```

- [ ] **Step 4: Commit**

---

### Task 5: 流水线监控面板

**Files:**
- Create: `web/src/views/PipelineMonitorPage.vue`
- Create: `web/src/components/pipeline/LayerProgress.vue`
- Modify: `web/src/router/index.js`

全透明可观测性面板。实时展示七层流水线每层状态，每个 AI prompt 和输出均可见。

**页面结构：**

```
┌─────────────────────────────────────────────────────────────┐
│  流水线监控 — 都市爱情故事 (run_abc123)                       │
├─────────────────────────────────────────────────────────────┤
│  七层进度:                                                   │
│  ⓪ 资产生成     ████████████ ✓ 完成  (3 角色 + 5 场景)       │
│  ① 资产工坊     ████████████ ✓ 完成  (审图通过率 87%)        │
│  ② 故事工坊     ████████████ ✓ 完成  (30 集剧本 + 圣经)      │
│  ③ 导演工坊     ████████████ ✓ 完成  (300 个分镜)            │
│  ④ 渲染引擎     ██████░░░░░░ 60%   (E18/30 渲染中)           │
│  ⑤ 质量审计     ░░░░░░░░░░░░ 0%    —                         │
│  ⑥ 后期包装     ░░░░░░░░░░░░ 0%    —                         │
│                                                             │
│  当前: E18-F5 渲染中 — Seedance 2.0 (5s 等待中)              │
│  成本: ¥12.34 | 耗时: 45min | 预计剩余: 30min                │
│                                                             │
│  ▼ 最近 AI 调用 (全透明):                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ [15:32] Seedance submit — prompt: "夜雨街头，男主..."   │   │
│  │ [15:33] Seedance poll   — status: running, 15%       │   │
│  │ [15:32] Gemini audit   — E17-F8 score: 87, pass      │   │
│  │ [15:30] DeepSeek LLM   — episode 20 storyboard done  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

- [ ] **Step 1: PipelineMonitorPage (~220 行) + LayerProgress (~80 行)**

- [ ] **Step 2: 添加路由**

```js
{ path: 'pipeline/:runId', name: 'PipelineMonitor', component: () => import('../views/PipelineMonitorPage.vue') },
```

- [ ] **Step 3: Commit**

---

### Task 6: 菜单 + 导航整合

**Files:**
- Modify: `web/src/views/AdminLayout.vue` — 侧边栏菜单

在侧边栏添加「AI 视频工坊」分组，包含：
- AI 模型配置 (`/ai-config`)
- 角色资产库 (`/characters`)
- 场景资产库 (`/scenes`)
- 系列管理 (`/series`)
- 流水线监控（动态链接）

---

## Plan C 总结

| Task | 内容 | 文件 | 行数 |
|------|------|------|------|
| 1 | API 客户端层 (5 modules) | new | ~80 |
| 2 | AI 模型配置中心页 | new + modify | ~270 |
| 3 | 角色资产库页 + CharacterCard | new + modify | ~250 |
| 4 | 系列列表 + 详情页 + EpisodeList | new + modify | ~480 |
| 5 | 流水线监控面板 + LayerProgress | new + modify | ~320 |
| 6 | 菜单整合 | modify | ~20 |

**Plan C 总工作量：约 1420 行，2-3 天。**

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | — | — | 0 | — | — |
| CEO Review | — | — | 0 | — | — |
| Design Review | — | — | 0 | — | — |
| Codex Review | — | — | 0 | — | — |

**VERDICT:** NO REVIEWS YET — run `/autoplan` or `/plan-eng-review` after Plan C to lock.
