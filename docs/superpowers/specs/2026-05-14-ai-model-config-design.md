# AI 模型配置中心 — 设计方案

## 目标

将 AI 模型配置从 SystemSetting 键值对方案升级为独立数据模型 + CRUD 管理页面。每种模型有专属参数集（LLM 有 thinking 参数，Video 有 resolution 参数等），替代硬编码的 flat key-value。

PipelineLayerConfig 的下拉选项也从 AIModel 表动态拉取，替代 reference_data 字典方案。

## 数据模型

### AIModel 表

```python
class AIModel(Base):
    __tablename__ = "ai_models"

    id          = Column(String(36), PK, UUID)
    name        = Column(String(100), nullable=False)     # "DeepSeek V3"
    model_type  = Column(String(20), nullable=False)      # llm|image|video|tts|audit
    provider    = Column(String(30), nullable=False)       # deepseek|openai|seedance|kling|...
    base_url    = Column(String(300), nullable=True)       # API 端点
    api_key     = Column(String(500), nullable=True)       # 加密存储
    api_secret  = Column(String(500), nullable=True)       # 加密存储(Kling 双钥)
    model_name  = Column(String(100), nullable=True)       # deepseek-chat / seedance-2.0
    config_json = Column(JSON, nullable=True)              # 类型专属参数
    enabled     = Column(Boolean, default=True)
    sort_order  = Column(Integer, default=0)
    created_at  = Column(DateTime, default=bj_now)
```

### config_json 按类型

| model_type | config_json 字段 |
|-----------|-----------------|
| llm | `thinking_enabled`, `thinking_budget`, `max_tokens`, `temperature` |
| image | `default_size`, `default_quality` |
| video | `default_resolution`, `default_duration`, `default_aspect_ratio` |
| tts | `default_voice`, `default_language`, `default_speed` |
| audit | `audit_mode` (multi/single/batch) |

### api_key / api_secret 安全

- 存储前 AES 加密（复用现有 `app/services/crypto.py` 的 `encrypt/decrypt`）
- GET 列表时不返回 api_key 真实值，返回占位符 `"****"` 或空
- GET 详情时返回解密后的真实值（admin only）

## API 设计

```
GET    /api/ai-models             # 列表 (?model_type=llm&enabled=true)
GET    /api/ai-models/{id}        # 详情 (含解密 api_key)
POST   /api/ai-models             # 新增
PUT    /api/ai-models/{id}        # 更新
DELETE /api/ai-models/{id}        # 删除
GET    /api/ai-models/options     # 供 PipelineLayerConfig 拉取
```

### 兼容旧接口

现有 `/api/ai-config/models` (GET/PUT) 保留。新系统部署后，旧 AIConfigPage 中的 SystemSetting 值可通过一次性迁移脚本导入 AIModel 表。

## 页面设计

### 布局：左右分栏

```
┌────────────────────────────────────────────────────┐
│  模型配置中心                        [+ 新增模型]    │
├──────────────┬─────────────────────────────────────┤
│  左栏 280px  │  右栏 (自适应)                       │
│              │                                     │
│  ▸ 脚本生成   │  编辑：DeepSeek V3                   │
│    DeepSeek  │  ┌─────────────────────────────┐    │
│    GPT-4o    │  │ 通用配置                      │    │
│    Qwen Max  │  │ model_type: LLM              │    │
│  ▸ 画面生成   │  │ provider: deepseek            │    │
│    Seedance  │  │ base_url: https://api...      │    │
│    DALL-E 3  │  │ api_key: sk-****              │    │
│  ▸ 视频渲染   │  │ model_name: deepseek-chat     │    │
│    Seedance  │  └─────────────────────────────┘    │
│    Kling     │  ┌─────────────────────────────┐    │
│  ▸ 语音合成   │  │ LLM 专属配置                  │    │
│    Edge-TTS  │  │ thinking_enabled: ON          │    │
│    Index-TTS │  │ thinking_budget: 8192         │    │
│  ▸ 质量审计   │  │ max_tokens: 4096              │    │
│    GPT-4o    │  │ temperature: 0.7              │    │
│              │  └─────────────────────────────┘    │
└──────────────┴─────────────────────────────────────┘
```

### 交互行为

1. 左栏按 `model_type` 分组，选中项高亮
2. 点击"[+ 新增模型]"弹出选择 model_type 对话框，确认后右侧显示空白编辑表单
3. 编辑表单根据 `model_type` 动态显隐专属字段区域
4. `provider` 下拉选项也根据 `model_type` 动态变化：
   - llm: deepseek | openai | anthropic | custom
   - image: seedance | openai | comfyui | runninghub
   - video: seedance | kling | wan | pixelle
   - tts: edge-tts | index-tts | spark-tts | custom
   - audit: openai | gemini | local | none
5. api_key 输入用 `type="password"`，回显时显示解密值或占位符
6. 保存时仅 api_key 非空的字段加密写入

## 与 PipelineLayerConfig 联动

PipelineLayerConfig.vue 的 `onMounted` 改为：

```javascript
// 旧: listItems('llm_script_models') → reference_data
// 新: GET /api/ai-models/options?model_type=llm&enabled=true
```

返回格式：
```json
{
  "ok": true,
  "options": [
    {"id": "uuid", "name": "DeepSeek V3", "model_type": "llm", "provider": "deepseek"},
    {"id": "uuid", "name": "GPT-4o", "model_type": "llm", "provider": "openai"}
  ]
}
```

PipelineLayerConfig 的 `<select>` 展示 `name` 作为 label，`id` 作为 value。
当用户选好模型后，`pipeline_start` 下发 `model_ids: {"scriptLLM": "uuid", "imageModel": "uuid", ...}`，backend 根据 model_id 查询 AIModel 表获取 api_key/base_url 等完整配置调用 API。

## 默认数据 (seed)

seed 在 startup 调用，幂等（按 `(model_type, provider, model_name)` 唯一检查）：

| model_type | name | provider | model_name |
|-----------|------|----------|-----------|
| llm | DeepSeek V3 | deepseek | deepseek-chat |
| llm | GPT-4o | openai | gpt-4o |
| llm | Qwen Max | openai | qwen-max |
| llm | Claude Opus | anthropic | claude-opus-4-7 |
| image | Seedance Image | seedance | seedance-image |
| image | DALL-E 3 | openai | dall-e-3 |
| image | FLUX | comfyui | flux |
| video | Seedance 2.0 | seedance | doubao-seedance-2.0-260128 |
| video | Kling 3.0 | kling | kling-v1-6 |
| video | Wan 2.7 | wan | wan-2.7 |
| tts | Edge-TTS | edge-tts | edge-tts |
| tts | Index-TTS | index-tts | index-tts |
| tts | Spark-TTS | spark-tts | spark-tts |
| audit | GPT-4o Audit | openai | gpt-4o |
| audit | Gemini Audit | gemini | gemini-2.5-pro |
| audit | Skip Audit | none | — |

所有模型 `api_key` 默认为空，由用户在前端配置。`config_json` 按类型填充默认值。

## 迁移

现有 `SystemSetting` 中的 AI 配置键（`ai_config.py` 的 `AI_CONFIG_KEYS`）：
- llm_provider / llm_api_key / llm_base_url / llm_model → 迁移到 AIModel (llm, 默认一条)
- seedance_api_key / kling_access_key / kling_secret_key / runninghub_api_key → 迁移到对应 AIModel 的 api_key 字段
- 其余键 (oss_*, audit_*, comfyui_*) → 保留在 SystemSetting 中，不属于本次范围

迁移脚本在首次 startup 时执行：检测 AIModel 表为空时自动从 SystemSetting 导入。

## 文件清单

| 文件 | 操作 |
|------|------|
| `server/app/db_models.py` | 新增 AIModel 类 |
| `server/app/routers/ai_config.py` | 重写为 CRUD router + 迁移逻辑 |
| `server/app/main.py` | 更新 router 导入 |
| `web/src/views/AIConfigPage.vue` | 完全重写：左右分栏模型管理 |
| `web/src/api/aiConfig.js` | 新增 model CRUD 函数 |
| `web/src/components/video-studio/PipelineLayerConfig.vue` | 改为调用 `/api/ai-models/options` |
| `web/src/views/DictManagePage.vue` | 移除模型相关分类的种子数据（已废弃） |
| `server/app/routers/reference_data.py` | 移除 DEFAULT_DATA 中的模型分类 |

---

## GSTACK REVIEW REPORT — /plan-ceo-review 2026-05-14

### Completion Summary

| Section | Result |
|---------|--------|
| Mode | SELECTIVE EXPANSION |
| Premises | 6/6 ACCEPTED |
| Architecture | CLEAN — single table + JSON config, no new dependencies |
| Error/Rescue | CLEAN — IntegrityError on duplicate, encrypted storage, 404 on missing |
| Security | CLEAN — api_key encrypted at rest, admin-only endpoints |
| Data Flow | CLEAN — standard CRUD, api_key masked in list |
| Code Quality | CLEAN — follows existing patterns (crypto.py, reference_data CRUD) |
| Tests | ACCEPTED — 5-8 CRUD tests included in scope |
| Performance | CLEAN — single table, indexed queries |
| Observability | CLEAN — standard FastAPI logging |
| Deployment | CLEAN — Base.metadata.create_all for new table |
| Long-Term | CLEAN — reversible (drop table + git revert) |
| Design (Sec 11) | CLEAN — left-right split panel, dynamic form fields per model type |

### Accepted Expansions
- Model test connection button ("测试连接")

### Deferred
- Provider preset templates → TODOS.md

### Verdict
CEO + Design CLEAR — ready to implement

---

## Eng Review — /plan-eng-review 2026-05-14

### Step 0: Scope Challenge
8 files — complexity threshold triggered. All 8 confirmed necessary: new ORM model + CRUD router + UI rewrite + PipelineLayerConfig integration + cleanup of superseded dictionary system.

### Section 1: Architecture — CLEAN
Single AIModel table + JSON config for type-specific fields. Reuses crypto.py for encryption. No new dependencies. admin-only auth on all mutation endpoints.

### Section 2: Code Quality — CLEAN
Follows existing patterns: crypto.py encryption, reference_data.py CRUD structure. No DRY violations.

### Section 3: Test Review — 17 test points accepted
13 backend (pytest, new test_ai_config.py) + 4 frontend (Vitest, new ai-config.test.js).
Test plan artifact: ~/.gstack/projects/dy_auto/HNXE-feature-video-review-fixes-eng-review-test-plan-20260514-221137.md

```
NEW CODEPATHS — 17 total, 0 pre-existing coverage:
  GET  /api/ai-models          (3 tests)
  GET  /api/ai-models/{id}     (3 tests)
  POST /api/ai-models           (3 tests)
  PUT  /api/ai-models/{id}     (2 tests)
  DELETE /api/ai-models/{id}   (2 tests)
  GET  /api/ai-models/options   (1 test — implicit in CRUD tests)
  AIConfigPage.vue              (4 Vitest tests)
PipelineLayerConfig.vue         (INHERITED — existing onMounted pattern coverage)
```

### Section 4: Performance — CLEAN
Single-table query, indexed on model_type. No N+1. options endpoint: one filtered SELECT. No caching needed.

### Failure Modes
| Mode | Rescued? | Test? | User sees? |
|------|----------|-------|-----------|
| Duplicate model name+provider | Y (IntegrityError→409) | Y | "模型已存在" |
| Decrypt failure (corrupted key) | Y (log+fallback) | Y | 空白 api_key |
| Empty DB on options fetch | Y (empty array) | Y | 空下拉列表 |
| Invalid model_type enum | Y (Pydantic 422) | Y | "类型不合法" |

### Completion Summary
- Architecture: 0 issues
- Code Quality: 0 issues
- Test Review: 17 gaps → 17 test points accepted
- Performance: 0 issues
- NOT in scope: written (see CEO review)
- What already exists: written
- Failure modes: 0 critical gaps
- Parallelization: Sequential — DB model → Router → Frontend → PipelineLayerConfig cleanup

### Verdict
ENG CLEAR — 0 blocking issues, 17 test points committed to scope
