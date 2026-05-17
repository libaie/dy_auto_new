# 旅游评论意向地提取 — 设计规格

**日期**: 2026-05-15 | **分支**: feature/video-review-fixes | **决策方式**: /brainstorming

## 问题陈述

旅游行业线索挖掘中，评论用户会在评论中表达旅游意愿或提及目的地，当前系统只分析评论质量（分数/层级/意图），不提取目的地信息，造成线索价值丢失。

## 目标

在评论语义分析流程中增加两个字段：**意向城市（intended_city）** 和 **意向景点（intended_attraction）**，AI 从评论内容中提取目的地信息，结果落库。

## 核心规则

1. 评论明确提及地名（城市/景点/国家）→ 直接从评论提取
2. 评论提及具体景点但未说城市 → AI 推断所属城市
3. 评论有旅游意愿但未提及具体地名 → 两个字段为空字符串
4. 评论无旅游意愿 → 两个字段为空字符串

示例：评论"一直想去大理看看" → city=大理, attraction=大理古城

## 方案选择

**方案 A（选中）**: 扩展现有分析提示词，一次 AI 调用完成所有分析 + 目的地提取。

## 数据模型

### collected_comments 表新增字段

```sql
ALTER TABLE collected_comments ADD COLUMN intended_city VARCHAR(100);
ALTER TABLE collected_comments ADD COLUMN intended_attraction VARCHAR(200);
```

### CollectCommentData 模型

```python
class CollectCommentData(BaseModel):
    # ... existing fields ...
    intended_city: str | None = None
    intended_attraction: str | None = None
```

## 提示词模板变更

### 新增 destinationExtraction 规则块（可选顶级字段）

```json
{
  "destinationExtraction": {
    "enabled": true,
    "videoContextRole": "视频内容为目的地锚点",
    "rules": [
      "优先从评论原文提取明确的地名",
      "评论提及具体景点时推所属城市",
      "只有旅游意愿无地名时以视频内容兜底",
      "无旅游意愿时两个字段为空"
    ]
  }
}
```

### AI 分析 JSON 输出追加

```json
{ "score": 75, "tier": "high", "..., "intended_city": "安顺", "intended_attraction": "黄果树瀑布" }
```

## 设备端变更

| 文件 | 改动 |
|---|---|
| `ai-analyzer.js` | `_buildAnalysisPrompt()` 条件拼入 destinationExtraction 规则；`_parseAnalysisResponse()` 透传新字段 |
| `reply-comment.js` | `analyzeComment` 结果中的目的地字段传给 `generateDM` 和 `saveCommentAIReply` |
| `search-collect.js` | `_aiQualify` 存储 analysis 结果到 comment；`_collectCommentData` 附加目的地字段 |

## 服务端变更

| 文件 | 改动 |
|---|---|
| `db_models.py` | `CollectedComment` +2 列 |
| `models.py` | `CollectCommentData` +2 可选字段 |
| `prompt_template_service.py` | 校验放行 destinationExtraction |
| `prompt_templates.py` | `TEMPLATE_SCHEMA_DESC` 增加 destinationExtraction 结构 |

## 本地 fallback

`prompts-config.js` 中 travel 行业加 `destinationExtraction` 配置块。

## 数据流

```
评论 → analyzeComment() → AI 返回含 city/attraction → 落库
```

## CEO Review 扩展（SCOPE EXPANSION 已接受）

| # | 扩展 | 决策 |
|---|------|------|
| 1 | DM 目的地话术适配：`generateDM()` 传入 `intended_city`，破冰时自动带上目的地 | ACCEPTED |
| 3 | 前端采集列表展示意向地列 + 城市筛选 | ACCEPTED |
| 2 | 目的地热度统计 API + 排行面板 | DEFERRED → TODOS.md |
| 4 | 私信培育阶段按目的地注入攻略 | DEFERRED → TODOS.md |

### 扩展文件变更

| 文件 | 额外改动 |
|---|---|
| `ai-analyzer.js` | `generateDM()` 加 `intendedCity` 参数，prompt 拼入目的地信息 |
| `reply-comment.js` | `generateDM()` 调用时传入 `analysis.intended_city` |
| `web/src/components/DataTable.vue` | 采集视图加意向城市/意向景点列 + 城市筛选下拉框 |
| `web/src/api/` | `saveCommentAIReply` 签名加参数 |

## 非目标

- 不改变 health 行业提示词
- 不新增 AI 调用
- 不改变现有评分/回复逻辑
- 不新增目的地词典

---

## CEO Review 完成摘要

**模式**: SCOPE EXPANSION | **审查日期**: 2026-05-15

| 章节 | 状态 | 关键发现 |
|------|------|---------|
| 1. Architecture | CLEAN | 纯增量，无新耦合 |
| 2. Error & Rescue | 1 决策 | 缺失字段容错 → 空字符串 |
| 3. Security | CLEAN | AI 生成值非用户输入 |
| 4. Data Flow | CLEAN | videoText 为空是预期行为 |
| 5. Code Quality | CLEAN | 遵循现有模式 |
| 6. Tests | **1 GAP** | 加入实施计划：解析容错、签名、序列化测试 |
| 7. Performance | CLEAN | 无新调用 |
| 8. Observability | NOTE | 建议加 destination 字段提取日志 |
| 9. Deployment | CLEAN | nullable 列迁移安全 |
| 10. Long-term | CLEAN | 可逆性 4/5 |
| 11. Design | CLEAN | DataTable 列扩展 |

### 扩展决策
- **ACCEPTED**: DM 目的地话术适配、前端展示意向地列
- **DEFERRED**: 目的地统计面板、培育阶段目的地化 → TODOS.md

### 测试要求（加入实施计划）
1. `_parseAnalysisResponse` 对缺少 intended_city/attraction 的 JSON 容错
2. `analyzeComment` 接受 videoText 可选参数
3. `CollectReportRequest` 序列化含新字段
4. prompt 拼入 destinationExtraction 规则时输出的完整性

### 实施文件总览 (13 files)

| 层 | 文件 | 改动 |
|----|------|------|
| DB | `db_models.py` | CollectedComment +2 列 |
| API | `models.py` | CollectCommentData +2 字段 |
| API | `prompt_template_service.py` | 校验放行 |
| API | `prompt_templates.py` | TEMPLATE_SCHEMA_DESC 更新 |
| Device | `ai-analyzer.js` | analyzeComment/generateDM 签名扩展 |
| Device | `reply-comment.js` | 传入 videoText + destination |
| Device | `search-collect.js` | 传入 videoText + destination |
| Device | `prompts-config.js` | travel fallback 更新 |
| Device | `api-client.js` | saveCommentAIReply 签名 |
| Web | `DataTable.vue` | 意向地列 + 筛选 |
| Web | 采集 API | 字段透传 |
