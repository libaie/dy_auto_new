# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概要

抖音蓝V矩阵自动化运营平台，核心链路：搜索采集 → AI评论分析 → 拟人回复 → 关注 → DM私信引流。三层架构：设备端 (AutoJS) / 服务端 (FastAPI) / 前端 (Vue 3)。

## 常用命令

### 服务端 (server/)

```bash
# 启动开发服务器
cd server && python app/main.py                              # http://0.0.0.0:8000

# 运行全部测试
cd server && pytest                                           # 40+ 测试文件，asyncio_mode=auto

# 运行单个测试文件/用例
cd server && pytest tests/test_device_endpoints.py -v
cd server && pytest tests/test_device_endpoints.py::test_register -v

# 生产部署
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端 (web/)

```bash
cd web
npm run dev           # Vite dev server → http://localhost:3000，API 代理到 :8000
npm run build         # 生产构建 → web/dist/
npm run preview       # 预览生产构建
npx vitest            # 运行前端测试
```

### 设备端 (device/)

设备端脚本运行在 Android AutoJS6 (Rhino ES5.1) 环境中，不是 Node.js。`device/main.js` 是入口。打包脚本位于根目录 `_pack_device.py`，输出 `device-script.zip` 供设备下载。

## 架构

### 三层通信

```
前端 (Vue 3, :3000)  ──HTTP/SSE/WS──▶  服务端 (FastAPI, :8000)  ◀──HTTP poll/WS──  设备端 (AutoJS)
```

- **前端 ↔ 服务端**：REST API + SSE (AI 流式生成) + WebSocket (实时状态推送)
- **设备端 ↔ 服务端**：HTTP 轮询领任务 (`POST /api/device/poll`) + WebSocket 长连接 (接收推送)

### 服务端核心模块

| 模块 | 职责 |
|------|------|
| `app/domains/device_operations/device_router.py` | **设备端唯一 API 入口**：register / poll / report / selectors / templates / pairing。设备端所有 HTTP 调用都走这里 |
| `app/domains/account_operations/channels_router.py` | **频道管理**：关键词分组 → 账号轮转 → 任务队列生成 → 设备领任务 |
| `app/domains/account_operations/channel_service.py` | **频道调度引擎**：claim item / complete item / stale recovery / 每日配额检查。最核心的业务逻辑 |
| `app/domains/task_operations/task_service.py` | **任务调度引擎**：创建任务、重试计数、超时恢复、状态机 (pending→queued→running→completed/failed) |
| `app/domains/model_configuration/ai_generator.py` | **AI 生成服务**：多 Provider 支持 (DeepSeek/OpenAI/Anthropic)，含 thinking 级别控制和流式输出 |
| `app/domains/selector_management/selector_service.py` | **UI 选择器分发**：按 platform_version + resolution_profile 择优下发，支持新分辨率自动标定 |
| `app/domains/selector_management/template_service.py` | **模板图片管理**：多分辨率子目录，设备端以图找图所需的模板图片 |
| `app/domains/model_configuration/ai_models_router.py` | AI 模型配置 (llm_* 新命名优先，ai_* 旧命名 fallback) |
| `app/domains/pixelle_integration/pixelle_router.py` | Pixelle 图生视频集成 (含代理路由) |
| `app/domains/content_collection/dm_sequences_router.py` | DM 私信序列模板 + AI 生成 + 变体轮替 |
| `app/domains/script_pipeline/pipeline_router.py` | 视频 pipeline 编排 (角色→场景→系列→剧集→生成) |
| `app/ws_manager.py` | WebSocket 双通道：设备通道 (pair_ws) + 管理端通道 (admin_ws)，含心跳和离线检测 |
| `app/main.py` | 应用入口 + CORS + 全局异常日志中间件 + 后台离线检测器 + 卡死任务回收 |

### 设备端核心模块

| 模块 | 职责 |
|------|------|
| `device/core/task-executor.js` | **任务执行引擎**：Handler 注册表，通过 `executeTask()` 分发到具体 handler |
| `device/core/api-client.js` | **HTTP 客户端**：poll/report/download/模板同步，含离线队列、代理配置、自动重试 |
| `device/core/device-ws.js` | **WebSocket 客户端**：持久连接，接收服务端推送 (任务/取消/选择器更新/配置变更) |
| `device/core/ui-operator.js` | **UI 操作**：找元素/点击/以图找图 (`images.findImage`)/链式查找/手势滑动 |
| `device/core/selector-resolver.js` | **策略链解析引擎**：服务端下发的 JSON 策略链 → 按序尝试匹配 UI 元素 |
| `device/core/anti-detect.js` | **反检测**：随机延迟/拟人停顿/贝塞尔曲线手势/skip disabled |
| `device/core/calibrator.js` | **自动标定**：截图裁剪上传 → 服务端自动创建对应分辨率的 selector |
| `device/core/flow-context.js` | **页面流上下文**：运行时追踪业务环节，区分不同路径进入的同一页面 |
| `device/handlers/*.js` | **业务 Handler**：nurture / reply-comment / search-collect / search-comment / search-dm / search-like |

设备端是 ES5.1 环境，**没有** `let`/`const`/箭头函数/Promise/模板字符串。只能用 `var`、`function`、回调。通过 `require()` 加载模块，`device/main.js` 作为入口。

### 前端结构

- **路由** (`src/router/index.js`)：登录页 + AdminLayout 下 20+ 子路由
- **状态管理** (`src/stores/`)：Pinia — `auth.js` (认证) + `toast.js` (通知)
- **API 层** (`src/api/`)：按模块拆分 25 个文件，`client.js` 为 Axios 实例 + 拦截器
- **组合式函数** (`src/composables/`)：`usePolling` / `useWebSocket` / `usePagination` / `useConfirm` / `useDialog`
- **组件** (`src/components/`)：layout (侧边栏/顶栏/页面容器) + ui (Button/Dialog/Input/Select/Badge) + business (ChannelCard/TaskCreateDialog) + video-studio (13 个视频工作室组件)
- **样式**：Tailwind CSS 4 + `src/style.css`

## 数据库

- **开发**：SQLite (`server/app/data/dy_auto.db`)，WAL 模式，外键启用
- **生产**：MySQL（通过 `DATABASE_URL` 环境变量切换）
- **ORM**：SQLAlchemy 2.x，模型定义在 `server/app/db/models/`，统一从 `app.db.models` 导入 (72 张表)
- **迁移**：Alembic (`server/alembic.ini`)，`server/scripts/version.txt` 为设备端脚本版本

## 关键设计决策

1. **频道调度引擎**是最核心的业务逻辑：关键词 → Channel → ChannelItem → 设备 poll 领任务 → 执行 → report → complete。调度在 `channel_service.py`，任务生命周期在 `task_service.py`
2. **多分辨率 UI 适配**：选择器按 `platform_version` + `resolution_profile` 择优下发，新设备可自动标定
3. **设备端 ES5.1 限制**：设备端代码必须兼容 Rhino 引擎，不能使用任何 ES6+ 语法
4. **AI 配置优先级**：DB (`llm_*` keys) > DB (`ai_*` 旧 keys) > 环境变量
5. **服务端同时提供 REST 和 WebSocket**：设备端用 HTTP poll 领任务 + WS 收实时推送；管理端用 SSE 收 AI 流式 + WS 收设备状态
6. **所有时间用北京时间 (UTC+8)**：`bj_now()` 返回 naive datetime，存储在 DB 中统一使用

## 环境变量 (关键)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///...` | 生产环境切 MySQL |
| `DEVICE_SECRET` | `change-me-...` | 设备配对密钥，生产必改 |
| `ADMIN_PASSWORD` | `admin123` | 管理员密码，生产必改 |
| `JWT_SECRET` | `change-me-...` | JWT 签名密钥，生产必改 |
| `AI_API_KEY` | (空) | AI API Key (DeepSeek/OpenAI) |
| `AI_BASE_URL` | `https://api.deepseek.com` | AI API 地址 |
| `AI_MODEL` | `deepseek-chat` | AI 模型名 |
