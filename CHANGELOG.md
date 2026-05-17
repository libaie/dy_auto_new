# Changelog

## [0.1.0] - 2026-05-17

### Added
- 多控件 AND 页面检测：选择器系统新增 `page_detect` 目的类型，所有策略同时匹配才判定页面命中
- 流程上下文状态机 (flowContext)：运行时追踪业务环节，区分不同路径进入的同一页面
- SaaS P1 多用户认证与数据隔离：User 表 + bcrypt 登录 + JWT role 鉴权，非 admin 自动 scope 过滤
- 用户管理页面：admin 可注册/启用/禁用/删除用户，含路由守卫
- 多分辨率选择器 profile 系统：服务端按设备分辨率返回匹配选择器和模板，跨设备部署不再失效
- 新设备自动标定流程：设备端截图裁剪上传 → 服务端自动创建对应分辨率的 selector
- 全局异常日志中间件：捕获未处理 500，记录完整 traceback
- 通道编辑功能：可中途修改执行设备、账号、分组，含批量编辑和同步到存量子项选项

### Fixed
- 评论处理器零评论视频键盘弹出问题：5 个 handler 统一加评论数预检（含 desc() 纯文本无数字归零）
- 换视频时残留旧评论面板导致误操作：进入视频前加 is_comment_view 守卫
- is_comment_end 检测时机错误：从循环开头移到 swipe 后，首个 scroll 批次不跳过
- _openSearch 返回 true 但未进入搜索页：3 条返回路径全部加 isOnPage 验证
- 硬编码 accounts.yaml seed 导致删掉的 acc-001 重启后重建 + FK 级联 500 错误
- flowContext 状态在任务间泄漏 / _enterCommenterProfile 回退路径 / AI 臆想硬编码选择器
- auth.js 用户列表 API 路径 / verify_ws_admin_token 元组解包 / devices.py count 过滤
- list_all_items 自动种子导致 27 倍重复 / TopNav 分类标签不可点击 / conftest auth override

### Changed
- 导航栏整合：20 个扁平项 → 5 个分类组
- 悬浮窗美化：极光渐变球体 + CardView 阴影 + 弹性回弹动画
- 悬浮窗新增强制停止进程入口 + 等待弹窗支持关闭
- 搜索处理器重构：页面检测全部走 isOnPage/detectPage + flowContext
- Pipeline 模型选项：硬编码 → DB 动态读取
- 搜索输入框限定屏幕上方 30% 区域查找
- 回复评论处理器删除约 120 行本地硬编码页面检测

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
