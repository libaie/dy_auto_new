# 抖音自动化助手 - 设计文档

## 概述

基于 AutoJS6 的抖音自动化助手，支持批量多账号管理、多设备分布式运行。核心功能包括养号、关键词搜索、评论、点赞、评论回复、私信。不涉及数据采集。

## MVP 定义

**MVP = 单设备 + 单账号 + 养号功能 + 配置文件驱动（无 Web 后台）**

目标：在 1-2 周内验证 AutoJS6 操控抖音的核心可行性。

MVP 范围：
- FastAPI 后端（单设备模式，无需设备注册/调度）
- AutoJS6 设备端：刷推荐页、关注用户、基础互动
- 基础反检测：随机延迟、拟人滑动
- 配置文件管理（JSON/YAML），无 Web 管理后台（Vue 前端）

MVP 之后按实施顺序逐步扩展到多设备、Web 后台、AI 集成。

## 成功指标

| 指标 | MVP 目标 | 完整版目标 |
|------|---------|-----------|
| 养号存活率 | 连续 7 天运行无风控 | 连续 30 天运行无风控 |
| 操作成功率 | UI 操作成功率 > 85% | UI 操作成功率 > 95% |
| 系统稳定性 | 单设备连续运行 > 4 小时无崩溃 | 多设备连续运行 > 24 小时 |
| 任务完成率 | - | 每日任务完成率 > 90% |

## 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 抖音 UI 更新导致控件定位失效 | 高 — 操作大面积失败 | 高 — 抖音频繁迭代 | 后端管理选择器配置（ui_selectors 表），Web 后台热更新，设备自动同步；多策略降级（text→id→desc→coordinate） |
| 账号被风控/封禁 | 高 — 账号损失 | 中 — 取决于反检测效果 | 保守的操作频率上限；风控检测自动停止；账号分批使用 |
| AutoJS6 在某些设备上不稳定 | 中 — 任务中断 | 中 | 异常自动恢复；崩溃重启机制；设备兼容性测试 |
| 抖音灰度发布导致不同设备 UI 不一致 | 中 — 部分设备操作失败 | 中 | 设备级别的 UI 配置覆盖；灰度检测和适配 |
| AI 生成内容质量不可控 | 低 — 评论效果差 | 中 | 人工审核队列；敏感词过滤；模板兜底 |

## 架构

### 整体架构：轮询式

```
┌─────────────────────────────────────────────────────┐
│                   Web 管理后台 (Vue)                  │
│   账号管理 / 任务配置 / 选择器管理 / 状态监控 / 日志    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP API
┌──────────────────────▼──────────────────────────────┐
│                Python 后端 (FastAPI)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐     │
│  │ 任务调度器 │ │ 账号管理  │ │ AI内容生成服务    │     │
│  └────┬─────┘ └──────────┘ └──────────────────┘     │
│  ┌──────────┐ ┌──────────┐                           │
│  │选择器管理  │ │ 代理管理  │                           │
│  └────┬─────┘ └──────────┘                           │
│       │                                              │
│  ┌────▼─────────────────────────────────────────┐    │
│  │             SQLite 数据库 (可切换PG)            │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────▲──────────────────────────────┘
                       │ HTTP 轮询 (每10秒)
                       │ (任务 + 选择器版本 + 心跳)
┌──────────────────────┴──────────────────────────────┐
│              AutoJS6 设备端 (N台设备)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐     │
│  │ 任务执行器 │ │ UI操作层  │ │ 反检测引擎        │     │
│  └──────────┘ └──────────┘ └──────────────────┘     │
│  ┌──────────┐                                         │
│  │选择器加载器│                                         │
│  └──────────┘                                         │
└─────────────────────────────────────────────────────┘
```

**数据流**：
- 任务流：Web 后台创建任务 → 后端存入数据库 → 设备轮询获取待执行任务 → 设备执行并上报结果 → 后端更新状态 → Web 后台实时展示
- 选择器流：Web 后台编辑选择器 → 后端更新 `ui_selectors` 表 → 设备轮询时检测版本变更 → 增量拉取最新选择器 → UI 操作层使用新选择器执行任务

---

## 模块设计

### 1. Python 后端 (FastAPI)

#### 1.1 账号管理

- 账号 CRUD：昵称、抖音号、绑定设备、状态（正常/风控中/封禁）
- 账号分组：按用途分组（养号组、推广组）
- Cookie/Token 管理：存储每个账号的登录态，支持手动更新
- **Cookie 加密存储**：使用 AES-256-GCM 加密后存入数据库，运行时解密。加密密钥从环境变量 `COOKIE_SECRET` 读取，不入库

#### 1.2 任务调度器

**任务类型**：
- `nurture`：养号（刷推荐、关注、互动）
- `search_comment`：搜索后评论
- `search_like`：搜索后点赞
- `search_dm`：搜索后私信
- `reply_comment`：评论回复

**任务模型**：
```
Task {
  id: UUID
  type: enum (nurture | search_comment | search_like | search_dm | reply_comment)
  account_id: FK -> accounts
  device_id: FK -> devices
  params: JSON {
    keyword: string        // 搜索关键词
    target_url: string     // 目标视频/用户链接
    content_template_id: FK -> content_templates
    count: number          // 操作数量
    duration: number       // 养号时长(分钟)
  }
  status: enum (pending | running | completed | failed | cancelled)
  scheduled_at: datetime
  started_at: datetime
  completed_at: datetime
  result: JSON {
    success_count: number
    fail_count: number
    details: string
  }
}
```

**调度逻辑**：
- 设备通过 `GET /api/device/poll?device_id=xxx` 轮询，后端按设备绑定的账号分配优先级最高的 pending 任务
- **任务分配防竞态**：使用数据库乐观锁 — `UPDATE tasks SET status='running', device_id=? WHERE id=? AND status='pending'`，通过 affected rows 判断是否分配成功
- **任务超时恢复**：running 状态超过 30 分钟（可配置）且设备心跳中断的任务，自动重置为 pending。最大重试 3 次，超过后标记为 failed
- 每个账号有每日操作上限（防风控），调度器自动计算剩余配额，超限任务推迟到次日
- 支持定时任务：指定执行时间窗口（如每天 9:00-11:00）
- 同一账号同一时间只分配一个任务

**每日操作上限配置**：
- 配置来源：`daily_limits` 字段存储在 `accounts` 表中，JSON 格式
- 默认值（可在 config.py 中全局配置）：
  ```json
  {
    "likes": 50,
    "comments": 20,
    "follows": 20,
    "dms": 10,
    "replies": 15
  }
  ```
- 超限行为：推迟到次日执行，不丢弃任务，在 Web 后台显示"配额不足"状态
- 可按账号单独覆盖默认值

#### 1.3 AI 内容生成

- 对接 Claude/GPT API
- 输入：内容模板 + 上下文（视频标题、评论内容等）
- 输出：生成的评论/私信文本
- 内容模板支持变量替换：`{keyword}`、`{username}`、`{video_title}`
- 生成后检查敏感词，命中则重新生成

#### 1.4 数据库

默认使用 SQLite（开发简单、零部署），通过 SQLAlchemy 抽象层支持切换到 PostgreSQL。使用 Alembic 管理数据库迁移。

**数据库选型规则**：
- 单设备开发/测试：SQLite 足够
- 2 台及以上设备：**必须切换 PostgreSQL**，SQLite 的写锁机制在并发轮询+上报场景下会频繁 `SQLITE_BUSY`
- 切换方式：修改 `.env` 中的 `DATABASE_URL` 即可，SQLAlchemy + Alembic 保证兼容

**数据模型**：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `accounts` | 账号信息 | id, nickname, douyin_id, group, status, cookie, daily_limits |
| `devices` | 设备信息 | id, name, ip, status, bound_account_id, proxy_config, last_seen_at |
| `tasks` | 任务记录 | id, type, account_id, device_id, params, status, result |
| `task_templates` | 任务模板 | id, name, type, default_params |
| `content_templates` | 内容模板 | id, name, category, body, variables |
| `operation_logs` | 操作日志 | id, task_id, action, detail, timestamp |
| `daily_stats` | 每日统计 | id, account_id, date, likes, comments, follows, dms |
| `ui_selectors` | UI 选择器配置 | id, action_name, platform_version, strategies(JSON), version, enabled |

#### 1.5 认证机制

**管理端 API**：
- 使用 API Key 认证，请求头 `X-API-Key: <key>`
- API Key 在首次启动时自动生成，写入 `.env` 文件
- Web 后台登录：简单的用户名密码认证，JWT token 有效期 24 小时

**设备端 API**：
- 设备注册时需要提供预共享 secret（配置在设备端 `config.js` 中）
- 后端验证 secret 后分配 device_id，后续请求通过 device_id + 签名认证
- 签名方式：`HMAC-SHA256(device_id + timestamp, device_secret)`，timestamp 有效期 5 分钟

---

### 2. AutoJS6 设备端

#### 2.1 任务执行器 (TaskExecutor)

主循环逻辑：
```
while (true) {
  task = pollServer(deviceId)
  if (task) {
    handler = getHandler(task.type)
    result = handler.execute(task.params)
    reportResult(task.id, result)
  }
  sleep(pollInterval)
}
```

任务处理器按类型分离：
- `NurtureHandler`：养号
- `SearchHandler`：关键词搜索（视频/用户/话题）
- `CommentHandler`：评论/回复
- `LikeHandler`：批量点赞
- `DMHandler`：私信

#### 2.2 UI 操作层 (UIOperator)

封装抖音 App 的所有 UI 操作，基于 AutoJS6 控件查找 + 坐标点击：

| 方法 | 功能 |
|------|------|
| `openApp()` | 启动抖音 |
| `closeApp()` | 关闭抖音 |
| `searchKeyword(type, keyword)` | 搜索（type: video/user/hashtag） |
| `browseFeed(duration)` | 浏览推荐页指定时长 |
| `likeVideo()` | 对当前视频点赞 |
| `postComment(text)` | 发布评论 |
| `replyComment(text)` | 回复评论 |
| `sendDM(username, text)` | 发送私信 |
| `followUser(username)` | 关注用户 |
| `collectVideo()` | 收藏视频 |
| `shareVideo()` | 分享视频 |

每个操作返回 `{ success: boolean, error?: string }`。

**选择器动态加载机制**：

UIOperator 不硬编码选择器，而是从后端拉取 `ui_selectors` 配置。每个 UI 操作（如"点赞按钮"）对应多条定位策略，按优先级排列：

```json
{
  "action_name": "like_video",
  "strategies": [
    { "type": "text", "value": "赞", "priority": 1 },
    { "type": "id", "value": "com.ss.android.ugc.aweme:id/like_button", "priority": 2 },
    { "type": "desc", "value": "点赞", "priority": 3 },
    { "type": "coordinate", "x_percent": 0.85, "y_percent": 0.45, "priority": 4 }
  ]
}
```

策略类型：`text`（控件文本）、`id`（控件ID）、`desc`（内容描述）、`coordinate`（基于屏幕分辨率百分比的坐标）。

执行逻辑：按 priority 依次尝试，第一个匹配成功的策略生效。全部失败则上报任务失败并附带当前页面的控件树快照（用于后续分析和更新选择器）。

**选择器同步时机**：
- 设备启动时拉取全量选择器配置并缓存到本地
- 轮询任务时后端返回 `selectors_version`，版本不一致则增量更新
- 抖音 UI 变更时，运维人员在 Web 后台修改选择器配置，设备下次轮询自动生效，无需推送脚本

**设备覆盖**：支持按设备或抖音版本覆盖全局选择器（灰度发布场景）。`ui_selectors` 表的 `platform_version` 字段用于区分不同抖音版本的 UI 差异。

#### 2.3 反检测引擎 (AntiDetect)

**基础反检测**：
- 随机延迟：每个操作前后加 1-5 秒随机等待（可配置）
- 拟人滑动：贝塞尔曲线模拟真实手指轨迹，支持变速滑动
- 操作节奏波动：同类操作间隔 ±30% 随机波动
- 随机停顿：偶尔在操作间插入较长停顿（5-15秒），模拟用户走神

**高级反检测**：
- 设备信息伪装：修改 AutoJS6 可暴露的设备参数（Android ID、IMEI 等，需 root）
- IP 代理：每台设备绑定一个代理，存储在 `devices.proxy_config` 中（JSON 格式，含 `type`、`host`、`port`、`username`、`password`）。代理地址在 Web 后台设备管理页面配置，设备端轮询时通过心跳响应获取。不设独立代理池表 — 每设备一代理，简单够用
- 操作时间分布：模拟真实用户的活跃时间段（早中晚高峰），而非 24 小时均匀操作

#### 2.4 脚本更新机制

设备端启动时检查后端最新脚本版本号（`GET /api/device/script-version`），与本地版本对比：
- 版本一致：正常运行
- 本地版本较低：从后端下载最新脚本包（`GET /api/device/script-download`），解压覆盖后重启
- 更新过程记录日志，失败时使用旧版本继续运行

后端管理脚本版本：将设备端脚本打包为 zip，上传到后端，版本号递增。

#### 2.5 异常处理

- **UI 元素找不到**：最多重试 3 次，每次间隔递增（2s → 4s → 8s），全部失败则上报任务失败并附带控件树快照（`POST /api/device/report` 的 `ui_snapshot` 字段，包含当前页面所有控件的 text、id、desc、bounds），供运维分析后更新选择器配置
- **App 崩溃/ANR**：检测到抖音未响应时自动强杀重启，从断点继续
- **账号异常**：检测到验证码弹窗、风控提示时，立即停止当前任务，上报后端标记账号为"风控中"
- **网络异常**：本地缓存操作结果，网络恢复后批量上报

---

### 3. Web 管理后台 (Vue)

#### 页面结构

| 页面 | 功能 |
|------|------|
| **仪表盘** | 在线设备数、今日任务完成数、账号状态分布、异常告警 |
| **账号管理** | 账号 CRUD、分组管理、绑定设备、操作历史 |
| **设备管理** | 设备列表、在线状态、IP 代理配置、绑定账号 |
| **任务中心** | 创建任务、任务模板管理、定时任务、任务列表筛选 |
| **内容管理** | 内容模板编辑、AI 生成记录、敏感词库 |
| **数据统计** | 每日/周/月统计、账号维度趋势、任务成功率 |
| **选择器管理** | UI 选择器 CRUD、按操作分组、策略优先级排序、按抖音版本覆盖、设备端同步状态 |

#### 关键交互设计

**仪表盘实时更新**：前端每 10 秒轮询 `GET /api/stats/realtime`，获取最新设备状态和任务进度。后续可升级为 WebSocket 推送。

**任务创建流程**：
1. 选择任务类型（养号/搜索评论/搜索点赞/搜索私信/评论回复）
2. 配置任务参数（关键词、数量、模板等）
3. 选择执行账号（单选/多选/按分组）
4. 选择执行时间（立即/定时）
5. 确认创建

**错误和空状态**：
- 列表为空时显示引导文案和"创建第一个 XX"按钮
- 加载中显示骨架屏
- 请求失败显示错误提示 + 重试按钮
- 设备离线在列表中灰色标记

---

## API 接口

### 设备端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/device/register` | 设备注册（首次上线，需提供 secret） |
| GET | `/api/device/poll?device_id=xxx` | 轮询待执行任务 |
| POST | `/api/device/report` | 上报任务执行结果 |
| POST | `/api/device/heartbeat` | 设备心跳（每60秒） |
| GET | `/api/device/script-version` | 获取最新脚本版本号 |
| GET | `/api/device/script-download` | 下载最新脚本包 |
| GET | `/api/device/selectors?version=xxx` | 获取/增量更新 UI 选择器配置 |

**轮询响应示例**（`GET /api/device/poll`）：

有任务时：
```json
{
  "task": {
    "id": "uuid-xxx",
    "type": "search_comment",
    "params": {
      "keyword": "美食探店",
      "count": 10,
      "content_template_id": "tpl-001"
    }
  },
  "selectors_version": 5,
  "proxy": {
    "type": "http",
    "host": "proxy.example.com",
    "port": 8080
  }
}
```

无任务时：
```json
{
  "task": null,
  "selectors_version": 5
}
```

设备端收到响应后：如有任务则执行；如 `selectors_version` 与本地缓存版本不一致，调用 `/api/device/selectors` 增量更新选择器。

### 管理端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/api/accounts` | 账号管理 |
| CRUD | `/api/devices` | 设备管理 |
| CRUD | `/api/tasks` | 任务管理 |
| GET | `/api/tasks/templates` | 任务模板 |
| CRUD | `/api/content/templates` | 内容模板 |
| GET | `/api/stats/daily` | 每日统计 |
| POST | `/api/ai/generate` | AI 内容生成 |
| CRUD | `/api/selectors` | UI 选择器管理 |

---

## 项目目录结构

```
dy_auto/
├── server/                     # Python 后端
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── models/             # SQLAlchemy 模型
│   │   ├── routers/            # API 路由
│   │   │   ├── device.py       # 设备端接口
│   │   │   ├── accounts.py     # 账号管理
│   │   │   ├── tasks.py        # 任务管理
│   │   │   ├── selectors.py    # 选择器管理
│   │   │   ├── content.py      # 内容模板管理
│   │   │   └── stats.py        # 统计接口
│   │   ├── services/           # 业务逻辑
│   │   │   ├── scheduler.py    # 任务调度
│   │   │   ├── ai_generator.py # AI 内容生成
│   │   │   ├── anti_detect.py  # 反检测策略配置
│   │   │   └── selector_mgr.py # 选择器管理服务
│   │   └── config.py           # 配置
│   ├── requirements.txt
│   ├── alembic/                # 数据库迁移
│   ├── .env.example            # 环境变量模板
│   └── Makefile                # 常用命令
│       # make dev        — 启动开发服务器（uvicorn --reload）
│       # make migrate    — 执行数据库迁移（alembic upgrade head）
│       # make makemig    — 生成迁移文件（alembic revision --autogenerate）
│       # make test        — 运行测试（pytest）
│       # make seed        — 初始化默认选择器配置
│
├── web/                        # Vue 前端
│   ├── src/
│   │   ├── views/              # 页面
│   │   ├── components/         # 组件
│   │   ├── api/                # API 封装
│   │   └── stores/             # 状态管理
│   └── package.json
│
├── device/                     # AutoJS6 设备端脚本
│   ├── main.js                 # 入口，主循环
│   ├── core/
│   │   ├── task-executor.js    # 任务执行器
│   │   ├── ui-operator.js      # UI 操作层
│   │   ├── selector-loader.js  # 选择器动态加载
│   │   └── anti-detect.js      # 反检测引擎
│   ├── handlers/               # 任务处理器
│   │   ├── nurture.js
│   │   ├── search.js
│   │   ├── comment.js
│   │   ├── like.js
│   │   └── dm.js
│   ├── api/
│   │   └── client.js           # 与后端通信
│   └── config.js               # 设备配置
│
├── .env.example                # 全局环境变量模板
├── docker-compose.yml          # 可选：容器化部署
└── docs/
    └── superpowers/specs/      # 设计文档
```

---

## 实施顺序

建议按以下顺序分阶段实施：

0. **阶段零：MVP** — 单设备 + 单账号 + 养号 + 配置文件驱动，验证核心可行性
1. **阶段一：后端基础** — FastAPI 框架、数据库模型、账号/设备 CRUD API、认证机制
2. **阶段二：设备端基础** — AutoJS6 主循环、后端通信、基础 UI 操作层、脚本更新机制
3. **阶段三：核心功能** — 养号、搜索、评论、点赞、私信的 handler 实现
4. **阶段四：反检测** — 随机延迟、拟人滑动、代理支持
5. **阶段五：Web 后台** — Vue 仪表盘、任务管理、内容管理
6. **阶段六：AI 集成** — 内容模板、AI 生成、敏感词过滤
7. **阶段七：统计与优化** — 数据统计、性能优化、稳定性加固
