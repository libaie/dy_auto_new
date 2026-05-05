# 选择器策略卡片构建器设计

## Problem

选择器管理的「选择策略」字段当前是一个 JSON 数组 textarea。非技术人员（运营、助手配置人员）完全无法使用 — 不理解 JSON 语法、字段含义、优先级数字。即使有 tooltip 说明，学习成本仍然过高。

## Goal

将策略编辑从 JSON textarea 替换为可视化卡片构建器，同时保留 JSON 编辑模式供程序员使用。两种模式双向同步。

## Constraints

- 策略的 JSON 数据结构不变（`strategies: Array<{type, value?, priority, ...}>`）
- 不影响设备端选择器加载和执行逻辑
- 所有 7 种策略类型（text, id, desc, className, package, coordinate, image）同等易用
- 复用已有的模板图片上传功能

---

## UI 设计

### 模式切换

页面顶部有两个 tab：「表单模式」和「JSON 模式」。

```
┌─────────────────────────────────────────────────┐
│ 选择策略                    [ 表单模式 | JSON ]  │
├─────────────────────────────────────────────────┤
│                                                 │
│  ①  ☰ #1  [ text ▾ ]  输入框: "赞"        [×]  │
│                                                 │
│  ②  ☰ #2  [ id   ▾ ]  输入框: com.ss...   [×]  │
│                                                 │
│  ③  ☰ #3  [ image▾ ]  [选择文件] 阈值:0.8 [×]  │
│                                                 │
│         [ + 添加策略 ]                           │
│                                                 │
└─────────────────────────────────────────────────┘
```

- 默认「表单模式」
- 点「JSON」切到当前的 textarea
- 切回表单时自动解析 JSON；解析失败保留在 JSON 模式并提示错误
- 保存时始终从当前模式的 data 输出

### 策略卡片结构

每张卡片包含：

```
┌─────────────────────────────────────────────────────┐
│ ☰  #1   [ 类型下拉 ▾ ]                        [×]  │
│                                                     │
│   查找值:  [____________________________]           │
│                                                     │
│   ▸ 高级选项（可选偏移）                             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

- 左侧：拖拽手柄 `☰` + 自动编号 `#N`
- 顶部：类型下拉框（7 种类型可选）
- 主区域：根据类型动态显示对应字段
- 右上角：`×` 删除按钮
- 底部：折叠的「高级选项」（x/y 偏移）

### 类型与字段映射

| 类型 | 主字段 | 高级选项 |
|------|--------|----------|
| `text` | value（文本输入，placeholder: "例如：赞"） | x/y 偏移 |
| `id` | value（等宽字体，placeholder: "com.ss.android.ugc.aweme:id/..."） | x/y 偏移 |
| `desc` | value（文本输入，placeholder: "元素描述文字"） | x/y 偏移 |
| `className` | value（等宽字体，placeholder: "android.widget.TextView"） | x/y 偏移 |
| `package` | value（等宽字体，placeholder: "com.ss.android.ugc.aweme"） | x/y 偏移 |
| `coordinate` | x_percent（数字 0-100）+ y_percent（数字 0-100）并排 | 无 |
| `image` | template（文件选择 + 文本输入）+ threshold（滑块 0.5-1.0，默认 0.8） | x/y 偏移 |

- `coordinate` 类型不显示「查找值」，直接显示两个数字输入框并排
- `image` 类型的 template 字段旁有「选择文件」按钮，复用已有模板上传流程，上传后自动填入文件名
- 已有 image 策略的模板：沿用 `existingTemplates` 逻辑，卡片中直接显示缩略图预览
- 「高级选项」默认折叠，展开后显示 x_percent / y_percent 两个数字输入（0-100）

### 排序交互

- 每张卡片左侧有拖拽手柄 `☰`（桌面端拖拽排序）
- 同时提供 ▲/▼ 上下箭头按钮（移动端友好）
- 列表顺序即优先级，自动编号 `#1, #2, #3...`
- 保存时自动转为 `priority: index + 1` 写入 JSON

---

## 交互行为

### 添加策略

- 点击「+ 添加策略」按钮，在列表末尾追加新卡片
- 默认类型 `text`，用户可立即切换
- 添加后焦点落在类型下拉框

### 删除策略

- 卡片右上角 `×` 按钮，直接删除，无需确认
- 删除后自动重新编号

### 校验规则（保存时检查）

| 类型 | 必填字段 | 校验 |
|------|----------|------|
| text/id/desc/className/package | value | 非空 |
| coordinate | x_percent, y_percent | 0-100 范围 |
| image | template | 非空 |
| 所有类型 | — | 策略列表不能为空（至少 1 个） |

- 校验失败：对应卡片高亮红色边框 + 字段下方显示错误提示，阻止保存
- JSON 模式：解析失败在 textarea 下方显示错误信息，阻止保存

### 空状态

- 新建选择器：显示空列表 + 提示「点击下方按钮添加第一个查找策略」
- 编辑选择器且 strategies 为空：同上

### 模式切换边界

- 表单 → JSON：`strategyList` 数组序列化为带缩进的 JSON 字符串
- JSON → 表单：解析 JSON，如果不是数组或含未知 type，停留在 JSON 模式并提示错误

---

## 数据流

```
表单模式:
  strategyList (ref array) ←→ 卡片 UI
  保存时: strategyList → JSON.stringify → form.strategies → API

JSON 模式:
  form.strategies (string) ←→ textarea
  保存时: form.strategies → JSON.parse → API

模式切换:
  表单 → JSON: form.strategies = JSON.stringify(strategyList, null, 2)
  JSON → 表单: strategyList = JSON.parse(form.strategies)
  解析失败: 留在 JSON 模式，显示错误
```

## 不在范围内

- 设备端选择器加载逻辑（不受影响，JSON 结构不变）
- 选择器 CRUD API（不受影响）
- 策略类型新增或删除（只改 UI，不改数据模型）
- 移动端响应式布局（当前 Web 管理端主要在桌面使用）
