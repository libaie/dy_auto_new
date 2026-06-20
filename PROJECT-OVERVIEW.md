# 抖音自动化采集系统 (dy_auto) — 项目全景

## 核心业务

**抖音蓝V矩阵自动化运营平台**，以"评论回复→关注→私信（DM）→引流转化"为核心链路，实现从内容采集、AI 分析、拟人交互到数据统计的全流程自动化。

### 主要业务场景

| 场景 | 说明 |
|------|------|
| **搜索采集** | 关键词搜索 → 视频列表 → 逐视频进入评论区采集用户/评论数据 |
| **评论回复** | AI 分析评论意图 → 生成拟人回复 → 关注用户 → 发送 DM 私信引流 |
| **养号互动** | 搜索关键词 → 点赞/评论目标视频 → 模拟真人活跃行为 |
| **DM 私信** | 多消息序列发送（建立信任→短链→CTA），支持变体轮替防风控 |
| **用户采集** | 评论区进入个人主页 → 采集昵称/粉丝/获赞/性别/年龄/IP属地 → 持久化到数据中心 |
| **频道调度** | 关键词分组 → 账号轮转分配 → 任务队列 → 设备领任务 → 执行 → 上报 |

### 核心数据流

```
前端管理台 → 创建频道(关键词+账号+参数) → 服务端任务调度
  → 设备端 poll 领任务 → 打开抖音 → 搜索 → AI分析评论 → 回复 → 关注 → DM引流
  → 统计数据回传 → 前端实时看板
```

---

## 技术栈

### 服务端 (server/)
| 技术 | 用途 |
|------|------|
| **Python 3.12+** | 主语言 |
| **FastAPI** | Web 框架，REST API + SSE 流式 |
| **SQLAlchemy** | ORM，MySQL/SQLite 双后端 |
| **Pydantic v2** | 请求/响应模型校验 |
| **WebSocket** | 设备/管理端双向实时通信 |
| **Alembic** | 数据库迁移 |
| **httpx** | 异步 HTTP 客户端（调用 AI/外部 API） |

### 前端 (web/)
| 技术 | 用途 |
|------|------|
| **Vue 3** (Composition API) | 前端框架 |
| **Vue Router** | SPA 路由 |
| **Pinia** | 状态管理 |
| **Vite** | 构建工具 |
| **SSE (Server-Sent Events)** | AI 生成流式渲染 |

### 设备端 (device/)
| 技术 | 用途 |
|------|------|
| **AutoJS6 (Rhino ES5.1)** | Android 自动化引擎 |
| **Java 互操作** | FileOutputStream、UI Automator、PackageManager |
| **图像匹配 (images.findImage)** | 以图找图定位 UI 元素 |
| **OCR (PaddleOCR)** | 屏幕文字识别 |
| **HTTP 轮询 + WebSocket** | 服务端通信 |

### 基础设施
| 技术 | 用途 |
|------|------|
| **SQLite** (开发) / **MySQL** (生产) | 数据存储 |
| **Docker** | 容器化部署 |
| **GitHub Actions** | CI/CD |
| **Nginx** | 反向代理 |

---

## 目录结构

```
dy_auto/
├── device/                          # 📱 Android 设备端脚本 (AutoJS ES5.1)
│   ├── config.js                    #   设备基础配置（serverUrl, deviceId, deviceSecret）
│   ├── main.js                      #   入口：初始化 → 配对 → 轮询 → 任务调度
│   ├── project.json                 #   AutoJS 工程描述
│   ├── core/                        #   🧠 核心引擎
│   │   ├── ai-analyzer.js           #     AI 评论分析（意图识别 + 回复生成）
│   │   ├── anti-detect.js           #     反检测模块（随机延迟/拟人操作）
│   │   ├── api-client.js            #     HTTP 客户端（poll/report/download/模板同步）
│   │   ├── calibrator.js            #     自动标定（截图 → 上传 → 注册新分辨率模板）
│   │   ├── crash-recovery.js        #     崩溃恢复
│   │   ├── device-ws.js             #     WebSocket 客户端
│   │   ├── floating-window.js       #     悬浮窗日志
│   │   ├── flow-context.js          #     页面流上下文追踪
│   │   ├── pairing.js               #     设备配对流程
│   │   ├── prompt-template-loader.js#     提示词模板同步
│   │   ├── prompts-config.js        #     提示词配置
│   │   ├── selector-loader.js       #     UI 选择器同步 + 分辨率择优 + 自动标定触发
│   │   ├── selector-resolver.js     #     策略链解析引擎
│   │   ├── task-executor.js         #     任务队列执行器
│   │   ├── ui-operator.js           #     UI 操作（找元素/点击/以图找图/链式查找/手势）
│   │   └── update-checker.js        #     版本更新检测 + 下载 + 热更新
│   ├── handlers/                    #   📋 业务处理器
│   │   ├── base-handler.js          #     基类（safeClick/safeInput/页面导航/反检测钩子）
│   │   ├── comment-base.js          #     评论基类（打开评论区/滚动/采集评论+用户）
│   │   ├── comment-utils.js         #     评论工具（时间解析/去重/用户数据提取）
│   │   ├── nurture.js               #     养号任务（搜索→点赞/评论→不引流）
│   │   ├── reply-comment.js         #     评论回复任务（AI回复+关注+DM 完整链路）
│   │   ├── search-base.js           #     搜索基类（搜索页导航/排序/视频切换/消息发送）
│   │   ├── search-collect.js        #     搜索采集任务
│   │   ├── search-comment.js        #     搜索评论任务
│   │   ├── search-dm.js             #     搜索DM任务
│   │   └── search-like.js           #     搜索点赞任务
│   ├── utils/                       #   🔧 工具
│   │   ├── bezier.js                #     贝塞尔曲线手势模拟
│   │   └── logger.js                #     分级日志
│   ├── spike/                       #   实验/研究脚本
│   └── test/                        #   设备端测试脚本
│
├── server/                          # 🖥️ 服务端 (Python/FastAPI)
│   ├── requirements.txt             #   Python 依赖
│   ├── alembic.ini                  #   数据库迁移配置
│   ├── app/
│   │   ├── main.py                  #   入口：FastAPI 应用 + CORS + 后台离线检测 + AI 预热
│   │   ├── config.py                #   配置（北京时区、AI提供商、OSS等）
│   │   ├── database.py              #   数据库连接管理
│   │   ├── db/                      #   SQLAlchemy Base 与分域 ORM 模型
│   │   ├── deps.py                  #   依赖注入（auth/role/device 验证）
│   │   ├── models.py                #   Pydantic 请求/响应模型
│   │   ├── seed.py                  #   种子数据
│   │   ├── ws_manager.py            #   WebSocket 连接管理 + 心跳
│   │   ├── domains/                 #   🌐 分域 API 路由与业务服务
│   │   │   ├── accounts.py          #     账号 CRUD + 统计
│   │   │   ├── account_groups.py    #     账号分组管理
│   │   │   ├── ai_config.py         #     AI 配置
│   │   │   ├── audit.py             #     审核报告
│   │   │   ├── auth.py              #     登录/鉴权
│   │   │   ├── chains.py            #     链式模板 + 实例
│   │   │   ├── channels.py          #     频道管理（核心调度模块）
│   │   │   ├── characters.py        #     数字人角色
│   │   │   ├── content.py           #     内容模板
│   │   │   ├── data.py              #     数据中心查询
│   │   │   ├── device.py            #     设备端核心 API（poll/report/selectors/templates/配对）
│   │   │   ├── devices.py           #     设备管理
│   │   │   ├── director.py          #     导演模块
│   │   │   ├── dm_sequences.py      #     DM 私信序列模板 + AI 生成 + 变体
│   │   │   ├── pipeline.py          #     视频 pipeline 编排
│   │   │   ├── pixelle.py           #     Pixelle 图生视频
│   │   │   ├── prompt_templates.py  #     提示词模板 + AI 生成
│   │   │   ├── reference_data.py    #     参考数据
│   │   │   ├── scenes.py            #     场景配置
│   │   │   ├── seedance.py          #     Seedance 视频生成
│   │   │   ├── selectors.py         #     UI 选择器管理（多分辨率/多版本）
│   │   │   ├── series.py            #     系列/剧集
│   │   │   ├── settings.py          #     系统设置
│   │   │   ├── stats.py             #     统计数据
│   │   │   ├── tasks.py             #     任务管理 + 实时统计
│   │   │   └── videos.py            #     视频管理
│   │   ├── services/                #   🏗️ 业务服务层
│   │   │   ├── ai_generator.py      #     AI 生成服务（多 Provider 支持）
│   │   │   ├── chain_service.py     #     链式模板业务逻辑
│   │   │   ├── channel_service.py   #     频道调度引擎（核心：claim/complete/stale recovery/配额）
│   │   │   ├── content_service.py   #     内容模板变量替换
│   │   │   ├── crypto.py            #     加密工具
│   │   │   ├── device_service.py    #     设备注册/配对/在线管理
│   │   │   ├── industry_profile_service.py  # 行业合规配置加载器
│   │   │   ├── oss_service.py       #     OSS 文件上传
│   │   │   ├── pixelle_client.py    #     Pixelle API 客户端
│   │   │   ├── prompt_template_service.py  # 提示词模板管理
│   │   │   ├── script_service.py    #     设备脚本版本管理
│   │   │   ├── selector_service.py  #     UI 选择器管理（分辨率/版本择优）
│   │   │   ├── stats_service.py     #     每日统计（操作计数+配额检查）
│   │   │   ├── task_service.py      #     任务调度引擎
│   │   │   └── template_service.py  #     模板图片管理（多分辨率子目录）
│   │   ├── data/                    #   📊 数据文件
│   │   │   ├── dy_auto.db           #     SQLite 数据库
│   │   │   └── industry_profiles/   #     行业合规 Profile JSON（6个行业）
│   │   └── template_images/         #   🖼️ UI 模板图片（用于以图找图）
│   │       └── default/             #     默认分辨率模板
│   ├── scripts/                     #   运维脚本
│   │   ├── device-script.zip        #     设备端脚本打包
│   │   └── version.txt              #     当前版本号
│   ├── tests/                       #   服务端测试（pytest, 40+ 测试文件）
│   └── static/images/               #   静态资源
│
├── web/                             # 🌐 前端管理台 (Vue 3)
│   ├── index.html                   #   入口 HTML
│   ├── package.json                 #   依赖配置
│   ├── vite.config.js               #   Vite 构建配置
│   └── src/
│       ├── main.js                  #   入口：创建 App + Router + Pinia + 全局样式
│       ├── App.vue                  #   根组件
│       ├── api/                     #   🌐 API 客户端（按模块拆分，25 个）
│       │   ├── client.js            #     Axios 实例 + 拦截器
│       │   ├── auth.js / accounts.js / channels.js / devices.js / tasks.js ...
│       ├── router/
│       │   └── index.js             #   路由配置
│       ├── stores/
│       │   ├── auth.js              #     认证状态
│       │   └── toast.js             #     Toast 通知状态
│       ├── composables/             #   组合式函数
│       │   ├── useConfirm.js        #     确认对话框
│       │   ├── useDialog.js         #     通用对话框
│       │   ├── usePagination.js     #     分页
│       │   ├── usePolling.js        #     轮询
│       │   ├── useSavedPrompt.js    #     提示词缓存
│       │   └── useWebSocket.js      #     WebSocket 客户端
│       ├── constants/
│       │   ├── channels.js          #     频道状态常量
│       │   ├── content.js           #     内容类型常量
│       │   ├── navigation.js        #     导航菜单配置
│       │   └── tasks.js             #     任务状态常量
│       ├── utils/
│       │   └── format.js            #     格式化工具
│       ├── components/              #   通用组件
│       │   ├── layout/              #     布局（AppSidebar/AppTopNav/PageContainer）
│       │   ├── ui/                  #     UI 组件（AppButton/AppDialog/AppInput/AppSelect/AppBadge）
│       │   ├── business/            #     业务组件（ChannelCard/ChannelList/TaskCreateDialog）
│       │   └── video-studio/        #     视频工作室组件（13 个）
│       ├── views/                   #   页面（27 个页面）
│       │   ├── LoginPage.vue        #     登录
│       │   ├── DashboardPage.vue    #     仪表盘
│       │   ├── AccountsPage.vue     #     账号管理
│       │   ├── ChannelsPage.vue     #     频道管理
│       │   ├── TasksPage.vue        #     任务列表
│       │   ├── DevicesPage.vue      #     设备管理
│       │   ├── DataCenterPage.vue   #     数据中心
│       │   ├── DMSequenceManagePage.vue  # DM 序列管理
│       │   ├── PromptTemplatesPage.vue   # 提示词模板
│       │   ├── SelectorsPage.vue    #     UI 选择器管理
│       │   ├── StatsPage.vue        #     统计看板
│       │   ├── VideoStudio.vue      #     视频工作室
│       │   └── ...                  #     更多页面
│       └── __tests__/               #   前端测试
│
├── docs/                            # 📚 文档
│   ├── database-schema.md           #   数据库设计文档
│   └── adr/                         #   架构决策记录 (ADR, 4 篇)
│
├── device-project.md                # 📄 设备端完整源码（合并导出）
├── server-project.md                # 📄 服务端完整源码（合并导出）
├── web-project.md                   # 📄 前端完整源码（合并导出）
└── PROJECT-OVERVIEW.md              # 📄 本文件
```

---

## 架构特点

1. **三层分离**：设备端 (AutoJS ES5.1) / 服务端 (FastAPI) / 前端 (Vue 3)，通过 HTTP/WS 通信
2. **频道调度引擎**：关键词 → Channel → ChannelItem，支持账号轮转、每日配额、设备绑定、冷却时间
3. **多分辨率 UI 适配**：selector 按 `platform_version` + `resolution_profile` 择优下发，支持自动标定
4. **AI 驱动**：评论意图分析 + 回复生成 + DM 话术序列 + 变体轮替，全部由 AI 生成
5. **反检测**：贝塞尔曲线滑动、随机延迟、拟人停顿、skip disabled 机制
6. **崩溃恢复**：device crash recovery + server stale task recovery 双重保障

---

> 生成时间: 2026-05-20
