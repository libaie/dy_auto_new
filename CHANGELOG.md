# Changelog

## [0.1.0] - 2026-05-17

### Added
- 多控件 AND 页面检测：选择器系统新增 `page_detect` 目的类型，所有策略同时匹配才判定页面命中
- 流程上下文状态机 (flowContext)：运行时追踪业务环节（search→search_video→comment→profile→dm），区分不同路径进入的同一页面
- SaaS P1 多用户认证与数据隔离：User 表 + bcrypt 登录 + JWT role 鉴权，7 张业务表加 user_id FK，非 admin 自动 scope 过滤
- 用户管理页面：admin 可注册/启用/禁用/删除用户，含路由守卫
- 选择器管理前端新增"页面检测"分类标签和琥珀色标记
- 字典分类不再硬编码：前端完整 CRUD，数据从服务端字典表读取

### Fixed
- 修复 flowContext 状态在任务间泄漏（main.js 未 reset）
- 修复 _enterCommenterProfile 回退路径缺少 flowContext.enter("profile")
- 修复 AI 臆想硬编码选择器：删除 id("text1")、id("et7")、id("ivu") 等虚构 ID
- 修复 auth.js 用户列表 API 路径错误 (/users → /auth/users)
- 修复 verify_ws_admin_token 改为返回 (user_id, role) 元组后 pixelle.py/videos.py 未解包
- 修复 devices.py count 在 user_id 过滤前计算导致 operator 看到错误总数
- 修复 list_all_items 每次调用自动种子数据导致 27 倍重复
- 修复 TopNav 分类标签不可点击跳转
- 修复 conftest auth override 适配新的 verify_admin_token 元组返回格式

### Changed
- 导航栏整合：20 个扁平项 → 5 个分类组（运营/采集/AI 视频/数据中心/系统）
- Pipeline 模型选项：硬编码 JS 数组 → DB 字典表动态读取
- 搜索处理器重构：页面检测全部改用 isOnPage/detectPage + flowContext
- 回复评论处理器重构：删除约 120 行本地硬编码页面检测，统一走选择器系统
- DictManagePage UI 美化：玻璃态 + SVG 图标
- 搜索输入框限定屏幕上方 30% 区域查找，避免误匹配底部控件

---

## [0.0.99] - 2026-05-14

### Added
- AI 视频工坊新增分层模型配置 (PipelineLayerConfig)：脚本/画面/视频/语音/审计 5 层独立选模型
- 视频生成时可从角色资产库和场景资产库选择参考角色和场景
- 系列详情页支持 AI 一键自动生成角色和场景（基于 logline + LLM）
- 新增数据中心导出计划文档和参考数据唯一约束迁移

### Fixed
- P0: 流水线服务重启后可从 current_layer checkpoint 恢复，不再丢失执行进度
- P1: Pixelle-Video 代理层增加指数退避重试（3 次，2s/4s/8s），4xx 不重试
- P2: 视频轮询超时按模型差异化（Seedance 15min, Kling 10min, 其他 10min）
- P2: LLM JSON 解析改用括号计数算法，支持嵌套对象数组

### Changed
- 搜索采集处理器重构：支持多种策略组合，增强坐标兜底和反检测暂停
- 角色/场景/系列 API 增加批量操作和自动生成端点
- 数据中心页面支持动态字典系统和自定义字段导出

---

## [0.0.98] - 2026-05-13
- 前置版本
