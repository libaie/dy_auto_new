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
