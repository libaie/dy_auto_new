# 导航栏归纳设计方案

## 目标

将前端侧边栏 20 个平铺菜单项归纳为分组结构，降低视觉噪音，提升导航效率。

## 方案决策

| 决策点 | 选择 |
|--------|------|
| 归纳模式 | TopNav 分类切换 + 侧边栏上下文导航（VS Code 活动栏模式） |
| 分类颗粒度 | 5 组细粒度 |
| 侧边栏展开 | 保留现有 hover 展开（56px → 208px） |
| 默认分类 | 首页 `/` 默认"运营"，其余按路由自动映射 |
| 分类切换 | 路由驱动为主，手动点击 TopNav 标签可覆盖 |

## 5 分类与路由映射

```
运营  : /  /accounts  /account-groups  /devices
任务  : /tasks  /chain-templates  /chain-instances  /selectors
数据  : /data  /stats
AI视频: /video-studio  /series  /series/:id  /characters  /scenes
        /ai-config  /videos  /prompt-templates  /director/:seriesId/:episodeId
        /pipeline/:runId
系统  : /content  /dict-manage  /settings
```

## 子导航分组结构

NAV_ITEMS 从扁平数组改为分组结构：

```js
export const NAV_CATEGORIES = [
  {
    key: 'ops',
    label: '运营',
    items: [
      { name: '仪表盘', path: '/', icon: '...' },
      { name: '账号管理', path: '/accounts', icon: '...' },
      { name: '账号分组', path: '/account-groups', icon: '...' },
      { name: '设备管理', path: '/devices', icon: '...' },
    ],
  },
  {
    key: 'tasks',
    label: '任务',
    items: [
      { name: '任务中心', path: '/tasks', icon: '...' },
      { name: '任务链模板', path: '/chain-templates', icon: '...' },
      { name: '链实例', path: '/chain-instances', icon: '...' },
      { name: '选择器管理', path: '/selectors', icon: '...' },
    ],
  },
  {
    key: 'data',
    label: '数据',
    items: [
      { name: '数据中心', path: '/data', icon: '...' },
      { name: '数据统计', path: '/stats', icon: '...' },
    ],
  },
  {
    key: 'ai-video',
    label: 'AI 视频',
    items: [
      { name: 'AI 视频工坊', path: '/video-studio', icon: '...' },
      { name: '系列管理', path: '/series', icon: '...' },
      { name: '角色资产库', path: '/characters', icon: '...' },
      { name: '场景资产库', path: '/scenes', icon: '...' },
      { name: 'AI 模型配置', path: '/ai-config', icon: '...' },
      { name: '视频管理', path: '/videos', icon: '...' },
      { name: '提示词模板', path: '/prompt-templates', icon: '...' },
    ],
  },
  {
    key: 'system',
    label: '系统',
    items: [
      { name: '内容管理', path: '/content', icon: '...' },
      { name: '系统字典', path: '/dict-manage', icon: '...' },
      { name: '系统设置', path: '/settings', icon: '...' },
    ],
  },
]

// 路由 → 分类映射
export const ROUTE_CATEGORY_MAP = {
  '/': 'ops',
  '/accounts': 'ops',
  '/account-groups': 'ops',
  '/devices': 'ops',
  '/tasks': 'tasks',
  '/chain-templates': 'tasks',
  '/chain-instances': 'tasks',
  '/selectors': 'tasks',
  '/data': 'data',
  '/stats': 'data',
  '/video-studio': 'ai-video',
  '/series': 'ai-video',
  '/characters': 'ai-video',
  '/scenes': 'ai-video',
  '/ai-config': 'ai-video',
  '/videos': 'ai-video',
  '/prompt-templates': 'ai-video',
  '/content': 'system',
  '/dict-manage': 'system',
  '/settings': 'system',
}
```

`getCategoryByRoute` 匹配策略（按优先级）：
1. `ROUTE_CATEGORY_MAP[route.path]` 精确匹配（大部分静态路由命中）
2. `route.matched[0]?.path` 取路由定义中的路径模式进行匹配（动态路由如 `/series/:id` 命中 `/series`）
3. 兜底返回 `'ops'`

## 组件改动

### navigation.js
- `NAV_ITEMS` 扁平数组 → `NAV_CATEGORIES` 分组结构
- 新增 `ROUTE_CATEGORY_MAP` 路由映射表
- 新增 `getCategoryByRoute(route)` 工具函数

### AppTopNav.vue
- 移除 `navQuick` 4 个快捷链接
- 新增 `categories` prop（5 个分类标签）
- 新增 `activeCategory` prop（当前高亮分类）
- 点击分类标签 emit `update:activeCategory`

### AppSidebar.vue
- 接收 `activeCategory` prop
- 按 `activeCategory` 过滤 `NAV_CATEGORIES` 渲染
- 每个分类下渲染子项，分类标题作为视觉分隔

### AdminLayout.vue
- `computed` 从 `route` 计算 `activeCategory`
- 维护 `manualOverride` 状态（用户手动切分类时设 true，路由变化时重置 false）
- 下传 `activeCategory` 给 AppTopNav + AppSidebar

## 交互行为

1. **路由驱动（默认）**：`route` 变化 → `getCategoryByRoute(route)` → 更新 `activeCategory` → 侧边栏切换
2. **手动覆盖**：点击 TopNav 分类 → `manualOverride = true` → 侧边栏切换（不改路由）
3. **恢复路由驱动**：`route` 再次变化 → `manualOverride = false` → 回到路由驱动模式
4. **侧边栏展开**：hover 展开/收起逻辑不变

## 测试更新

navigation.test.js 需更新：
- `NAV_ITEMS` 引用 → `NAV_CATEGORIES`
- 新增 `ROUTE_CATEGORY_MAP` 覆盖测试
- 新增 `getCategoryByRoute` 单元测试
- 保留"无重复路径"和"所有项有 name/path/icon"断言

## 不改动

- 路由配置 `router/index.js` 不变
- 所有页面组件不变
- CSS/主题不变
- 侧边栏 hover 展开动画不变
- 暗色玻璃态风格不变

---

# GSTACK REVIEW REPORT — /autoplan 2026-05-14

## Phase 1: CEO Review — SELECTIVE EXPANSION

### 0A: Premise Challenge

| # | Premise | Verdict | Rationale |
|---|---------|---------|-----------|
| P1 | 20-item sidebar is excessive | ACCEPTED | User confirmed this is the pain point. 20 flat items without grouping creates scan fatigue. |
| P2 | VS Code activity bar is the right pattern | ACCEPTED WITH CAUTION | User chose C from 3 options. But both outside voices flag: the analogy maps to code modules, not operator workflows. |
| P3 | 5-group granularity is correct | ACCEPTED WITH CAUTION | Both voices note asymmetry: AI Video (10 routes) vs Data (2 routes). Taxonomy will age poorly. |
| P4 | Route-driven switching > manual | ACCEPTED | Route awareness eliminates a decision. Clean. |
| P5 | Hover-expand behavior preserved | ACCEPTED | Conservative choice — reduces risk. |

### 0B: Existing Code Leverage Map

| Sub-problem | Existing code | Reuse |
|-------------|--------------|-------|
| Nav item data | `navigation.js` NAV_ITEMS (flat array) | Restructure to NAV_CATEGORIES |
| Sidebar rendering | `AppSidebar.vue` (v-for over NAV_ITEMS) | Replace flat loop with nested category loop |
| TopNav quick links | `AppTopNav.vue` navQuick array | Replace with 5 category tabs |
| Route tracking | `AppTopNav.vue` already uses `useRoute()` | Extend to AdminLayout for category derivation |
| Layout | `AdminLayout.vue` passes no nav props | Add activeCategory as shared state |

### 0C: Dream State Delta

```
CURRENT         →  THIS PLAN       →  12-MONTH IDEAL
20 flat items    5 categorized      Operations cockpit:
                 route-driven       global ⌘K search,
hover sidebar    preserved hover    recent/favorites,
4 quick links    5 category tabs    user-customizable sidebar,
no search        no search          entity-centered nav,
manual scroll    filtered view      AI-suggested next page
```

### 0D: Mode — SELECTIVE EXPANSION

Auto-decided per autoplan rules. Scope is already focused (4 files). No expansion warranted.

### 0E: Temporal Interrogation

- **HOUR 1**: navigation.js restructured. Tests update. All 20 items preserved.
- **HOUR 2**: AdminLayout wired. Route→category derivation works.
- **HOUR 3**: AppTopNav category tabs replace navQuick. AppSidebar filters by category.
- **HOUR 4**: Integration testing. Edge cases: dynamic routes, 404, manual override states.
- **HOUR 5-6**: Bug fixes. manualOverride logic refinement.
- **6+ MONTHS**: New routes added without updating ROUTE_CATEGORY_MAP → drift. Taxonomy erosion as features grow. Possible rollback to flat list.

### CEO DUAL VOICES — CONSENSUS TABLE

```
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   MIXED   MIXED   DISAGREE*
  2. Right problem to solve?           NO      NO      CONFIRMED
  3. Scope calibration correct?        YES     YES     CONFIRMED
  4. Alternatives sufficiently explored? NO    NO      CONFIRMED
  5. Competitive/market risks covered? —       —       N/A (internal tool)
  6. 6-month trajectory sound?         MIXED   NO      DISAGREE*
═══════════════════════════════════════════════════════════════
* User Challenge: both models flag manualOverride as UX risk
* Taste Decision: taxonomy asymmetry (medium severity)
```

### CODEX SAYS (CEO — Strategy Challenge)

> "The VS Code analogy is weak. Douyin automation users think in workflows: launch tasks, monitor devices, fix failures, review output. The proposed groups reflect internal modules, not user jobs. Removing quick links may hurt high-frequency workflows. ROUTE_CATEGORY_MAP will drift as features grow — category ownership belongs with route metadata. The plan lacks success criteria."

### CLAUDE SUBAGENT (CEO — Strategic Independence)

> "Wrong problem definition. The actual issue is task switching latency. A 5-way category split forces a decision users shouldn't make. manualOverride auto-resetting on route change will be perceived as a bug. Zero user evidence cited. Asymmetric categories (10 vs 2) signal poor taxonomy. No success metric defined."

### Sections 1-10 Summary

| Section | Finding | Severity | Decision |
|---------|---------|----------|----------|
| 1. Problem Def | Both voices: "20 items" may not be the problem | HIGH | Proceed with plan since user confirmed + low-risk reversible change |
| 2. Error & Rescue | manualOverride auto-reset is confusing | HIGH | **Fix in plan**: remove manual override OR make it sticky. Recommend: route-driven only, no manual override |
| 3. UX Impact | Removing navQuick increases clicks for top-4 pages | MEDIUM | Keep quick links as first items in their categories |
| 4. Taxonomy Durability | ROUTE_CATEGORY_MAP will drift | MEDIUM | **Recommend**: move category to route meta in router/index.js |
| 5. Success Metrics | None defined | MEDIUM | Add before/after: time-to-find, misclick rate |
| 6. Scope | 4 files, focused | CLEAN | No adjustment needed |
| 7. Completeness | Missing loading states | LOW | Sidebar filters are instant synchronous — no loading needed |
| 8. Security | No new attack surface | CLEAN | N/A |
| 9. Performance | No new N+1, no network calls | CLEAN | N/A |
| 10. Rollback | Reversible — restore flat NAV_ITEMS | CLEAN | Low risk |

### Error & Rescue Registry

| Failure Mode | Likelihood | Impact | Rescue |
|-------------|-----------|--------|--------|
| manualOverride confusion | MEDIUM | User sees wrong sidebar for page | Remove override feature entirely |
| Dynamic route not matching | LOW | Falls through to 'ops' | Add explicit route.name mappings |
| New route forgotten in MAP | MEDIUM | Wrong category shown | Move category to route meta |
| Category tab overflow on small screens | LOW | Horizontal scroll on TopNav | Only 5 categories, fits 1280px+ |

### Failure Modes Registry

| # | Gap | Severity | Auto-Decision |
|---|-----|----------|---------------|
| FM1 | manualOverride creates dual-state confusion | HIGH | Remove manual override. Route-driven only. |
| FM2 | ROUTE_CATEGORY_MAP will drift | MEDIUM | Accept for now. Route meta migration is scope creep. |
| FM3 | No user validation before ship | MEDIUM | Deploy to staging, observe for 1 week |

### Phase 1 Completion Summary

- **NOT in scope**: Global search/⌘K, favorites/recent, user-customizable nav, route meta migration, analytics instrumentation
- **What already exists**: Full sidebar + TopNav in AdminLayout, route tracking via useRoute, glassmorphism theme
- **Dream state delta**: This plan moves from flat chaos → structured categories. Leaves search/favorites for future.
- **Decision Audit Trail**: See below

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| D1 | CEO | Remove manualOverride | Mechanical | P5 (explicit) | Both voices flag as UX bug | Keep override with sticky state |
| D2 | CEO | Keep ROUTE_CATEGORY_MAP separate from router | Taste | P3 (pragmatic) | Route meta migration is scope creep; 4-file plan stays focused | Move category to route meta |
| D3 | CEO | No success metrics for MVP | Taste | P3 (pragmatic) | Instrumentation is a separate feature; can add later | Require metrics before ship |
| D4 | CEO | 5-group taxonomy as-is | Taste | P6 (bias to action) | Perfect taxonomy doesn't exist; ship and iterate | Card-sort exercise first |
| D5 | CEO | Preserve hover-expand behavior | Mechanical | P3 (pragmatic) | User explicitly confirmed; no reason to change | Auto-expand on category switch |

---

## Phase 2: Design Review (UI Scope Detected)

### Design Litmus Scorecard

| Dimension | Score | Assessment |
|-----------|-------|------------|
| 1. Information Hierarchy | 7/10 | Categories add structure, but 2-item "数据" group is sparse. TopNav category tabs are well-placed. |
| 2. Interaction States | 5/10 | Missing: what does sidebar look like when route is unknown? Empty category display? |
| 3. Visual Consistency | 8/10 | Preserves existing glassmorphism theme. Category section headers need style definition. |
| 4. Responsive Strategy | 6/10 | 5 tabs fit on desktop. Plan doesn't address mobile or tablet — acceptable for operator tool. |
| 5. Accessibility | 5/10 | No keyboard nav for category tabs specified. SVG icons lack aria-labels. |
| 6. Error Prevention | 4/10 | manualOverride issue not addressed in plan. Dynamic route fallback to 'ops' may surprise users. |
| 7. User Feedback | 6/10 | Category switch has no visual transition. Active category highlight exists but transition isn't specified. |

### Design Findings

1. **Category section headers need visual design** (MEDIUM): The plan says "分类标题作为视觉分隔" but gives no mockup. Implementer will guess. **Fix**: Add a design spec line: `text-xs uppercase tracking-wider text-slate-400 px-4 pt-4 pb-1`.

2. **Empty "数据" category is sparse** (LOW): 2 items in one category feels incomplete. Accept for now — can merge with another category if needed.

3. **SVG icons need aria-labels** (LOW): Current icons have no accessible names. **Fix**: Add `aria-label` to each nav item.

### DESIGN DUAL VOICES — skipped (subagent + Codex unavailable for re-invocation, prior-phase voices already covered design concerns)

---

## Phase 3: Eng Review

### Architecture ASCII Diagram

```
AdminLayout.vue (NEW: activeCategory computed)
   ├── AppTopNav.vue (MODIFIED)
   │   └── CategoryTabs (REPLACES navQuick)
   │       ├── 运营 (ops) → emit update:activeCategory
   │       ├── 任务 (tasks)
   │       ├── 数据 (data)
   │       ├── AI视频 (ai-video)
   │       └── 系统 (system)
   │
   └── AppSidebar.vue (MODIFIED)
       └── Filtered by activeCategory
           └── NAV_CATEGORIES[activeCategory].items → v-for
               └── SectionHeader + NavItems

navigation.js (MODIFIED)
   ├── NAV_CATEGORIES[] (was NAV_ITEMS[])
   ├── ROUTE_CATEGORY_MAP{}
   └── getCategoryByRoute(route) → string

Dependencies:
   navigation.js ← AppSidebar.vue (import)
   navigation.js ← AdminLayout.vue (import getCategoryByRoute)
   AdminLayout → AppTopNav (prop: activeCategory)
   AdminLayout → AppSidebar (prop: activeCategory)
```

### Section 1: Architecture Assessment

The architecture is clean. AdminLayout is the natural owner of activeCategory state — it's the only component that wraps both TopNav and Sidebar. Data flows one direction: route → AdminLayout computed → props down. No circular dependencies. No new external dependencies.

**Verdict**: Sound. Coupling is minimal — only navigation.js knows about categories.

### Section 2: Code Quality

- **DRY**: NAV_ITEMS already a flat array. Restructuring to NAV_CATEGORIES preserves all existing data.
- **Naming**: `getCategoryByRoute` — clear. `manualOverride` — problematic (see D1). `NAV_CATEGORIES` — consistent with existing `NAV_ITEMS`.
- **Complexity**: Route matching is a 3-line function. No abstraction needed.

### Section 3: Test Review

**Test Diagram — Codepaths:**

| # | Codepath | Test Type | Covered? |
|---|----------|-----------|----------|
| 1 | `getCategoryByRoute('/')` → 'ops' | Unit | NEW — add to navigation.test.js |
| 2 | `getCategoryByRoute('/series/abc123')` → 'ai-video' (dynamic route) | Unit | NEW |
| 3 | `getCategoryByRoute('/unknown')` → 'ops' (fallback) | Unit | NEW |
| 4 | Sidebar renders correct items for activeCategory='tasks' | Component | NEW — Vitest |
| 5 | TopNav emits update:activeCategory on tab click | Component | NEW — Vitest |
| 6 | All 20 items still have name/path/icon after restructure | Unit | UPDATE existing test |
| 7 | No duplicate paths across all categories | Unit | UPDATE existing test |
| 8 | Series management before video management (existing test) | Unit | UPDATE — use new structure |

**Test Plan Artifact**: 8 test cases. 3 new unit tests. 2 new component tests. 3 updated existing tests.

### Section 4: Performance

No regression. Sidebar filtering is O(n) over 20 items — imperceptible. No network calls added. No watchers triggered beyond existing route reactivity. Category tabs are static markup.

### Section 5: Security

No new attack surface. All navigation remains client-side. No data exposed that wasn't already in the sidebar.

### ENG DUAL VOICES — simplified (single-model, Codex unavailable for fresh invocation)

Primary model assessment: Architecture is sound. The main implementation risk is the getCategoryByRoute fallback strategy for dynamic routes. Using `route.matched[0]?.path` is correct but depends on Vue Router internals — verify with integration test.

### Phase 3 Completion Summary

- Architecture: Clean. Unidirectional data flow. AdminLayout as single source of truth.
- Tests: 8 cases identified. Full coverage of static, dynamic, and fallback routes.
- Performance: No impact.
- Risk: LOW. Change is contained to 4 files. Reversible.

---

## Cross-Phase Themes

**Theme: manualOverride UX risk** — Flagged in Phase 1 (both voices) AND Phase 2 (error prevention score 4/10). High-confidence signal. **Recommendation**: Remove manualOverride. Route-driven only.

**Theme: Taxonomy durability** — Flagged in Phase 1 (Codex) AND implicit in Phase 2 (2-item data group). Medium-confidence. Accept for MVP, monitor.

---

## Review Scores Summary

| Review | Status | Key Finding |
|--------|--------|-------------|
| CEO | COMPLETE | 2 DISAGREE voices on premises; manualOverride flagged by both |
| Design | COMPLETE | 5/10 interaction states; missing visual spec for section headers |
| Eng | COMPLETE | Architecture sound; 8 test cases identified |
| DX | SKIPPED | No developer-facing scope |

- **CEO Voices**: Codex 10 concerns, Claude subagent 5 findings. Consensus 2/6 CONFIRMED, 2 DISAGREE → surfaced.
- **Design**: 7 dimensions scored. 3 issues (1 MEDIUM, 2 LOW).
- **Eng**: Architecture clean. Test plan: 8 cases. 0 performance/security issues.
- **DX**: N/A (internal UI refactoring, no API/CLI/SDK changes).

---

## Deferred to TODOS.md

| Item | Reason | Priority |
|------|--------|----------|
| Global ⌘K search | Out of scope — separate feature | P3 |
| Recent/favorites nav | Out of scope — requires analytics | P3 |
| Route meta migration (category in router) | Scope creep — separate refactor | P2 |
| Success metrics instrumentation | Deferred — add after MVP validation | P2 |
| Keyboard nav for category tabs | Accessibility — add in next iteration | P3 |
| User testing / card sort | No users available | P4 |
| Mobile/tablet responsive nav | Operator tool — desktop-first acceptable | P4 |
