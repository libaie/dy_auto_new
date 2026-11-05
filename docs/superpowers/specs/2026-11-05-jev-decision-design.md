# Jev 决策模型接入设计

## 目标和范围

将手机业务中的模型判断（评论评分、意图识别、内容相关性）接入 `typesafe-ai/jev`，请求固定发送到 `POST https://ai-gateway.vercel.sh/typesafe/v1/systemone`。回复、私信和视频文案仍由现有生成模型完成。保留现有多分辨率定位、发送确认和任务授权机制。

## 协议和配置

- 服务端新增 `POST /api/device/decision-proxy`，使用现有设备认证，接受 `{state, questions}`，由服务端注入模型和 Bearer 凭据。
- 使用原生 System One 的 `choice`、`score`、`noul`；不拼接 Chat Completions 路径，不发送 `messages`，不跟随重定向。
- 检查请求预算、问题类型和完整响应；数字必须有限且在有效范围内。分布必须包含预期键并且总和接近 1。允许响应使用供应商解析后的模型别名。
- 配置独立使用 `decision_*` 数据库键或对应 `DECISION_*` 环境变量：`enabled`、`api_key`、`api_url`、`model`、`min_confidence`、`min_probability`。
- 默认模型和完整 URL 固定为本次请求指定值；本次不支持任意供应商 URL，以免把网关凭据发送给其它服务。默认关闭；明确开启后即使缺少凭据，也保持开启状态并返回不可用，不能静默回退。
- 默认 `min_confidence=0.5`（score 原生 confidence），`min_probability=0.75`（choice 选中项概率、noul 布尔可信度）。两者是可调的初始业务门槛，并非经过业务数据校准的准确率保证。
- 服务端单次请求 connect 5 秒、其他阶段 15 秒；手机请求预算 25 秒。分类不主动进行应用级重复请求；认证、协议或不确定结果均跳过本次操作。
- `decision_api_key` 仅服务端使用。数据库写入使用现有加密模块，要求显式配置 `ENCRYPTION_KEY`；管理 API 返回掩码。空值和掩码均保留原密钥。设备只得到 enabled/model/thresholds，不得到密钥。

## 接口约定

服务端 `app.services.decision_config` 提供：

- `resolve_decision_config(db=None)`：完整服务端配置字典，字段为 enabled、api_key、api_url、model、min_confidence、min_probability；未配置 key 为空，错误配置抛出不含输入值的 `ValueError`。
- `get_public_decision_config(db=None)`：只包含 enabled/model/min_confidence/min_probability。配置错误时保持 enabled=true，让已启用设备跳过而不是回退。
- `get_decision_settings(db=None)`：管理页有效配置，键为带 decision_ 前缀的字符串；key 仅在存在时为 `****`，否则为空。
- `validate_decision_settings(updates)`：验证传入 decision_* 配置（非决策键忽略），错误抛出不含秘密值的 `ValueError`；允许空密钥/掩码以保留当前值。

配对、注册与轮询都在实际下发的配置对象内包含 `decision_config`；轮询必须放在 `device_config` 内，以匹配现有手机端配置应用入口。

手机在首次执行任务前，必须消费配对配置或取得注册/轮询的完整配置，并完成选择器及模板初始化。没有成功取得配置时，队列等待并继续同步，不把本地默认关闭视为服务端明确关闭。成功取得旧服务端完整配置但缺少决策字段时保持旧流程兼容。部分 WebSocket 配置更新不能被误当成完整的初始配置；显式决策字段除外。

## 手机业务行为

- Jev 开启时，评论分析生成原有 `score/tier/dimensions/reply` 结构。score 的原生区间为 `[0,N-1]`，先除以 `N-1` 再乘 100；tier 继续使用 40/70 分界。
- 动态行业模板提供评分规则、意图候选与语义上下文；问题说明本身包含语义，因为模型看不到问题 ID。
- 不新增人口属性推断；保留兼容结构的 unknown/mid 默认 profile。
- 评分、意图和 bot/competitor 判断不确定则返回 null。noul 的接近 0 表示明确否定，不能误当低置信度。
- 回复仅在需要时交给原生成模型，生成结果不能覆盖 Jev 的分数或意图。仅用于采集资格判断时跳过回复生成。
- `skip_reply:true` 的关注/私信任务也跳过评论回复生成。分享链接采集必须与普通采集一致，初始化当前任务模板并清除上一任务的覆盖配置。
- 相关性保留明确的本地关键词规则；需要模型时调用 Jev noul，不可用或不确定则不互动。
- 关闭 Jev 时保留旧行为，便于逐步上线。
- 所有手机生产代码兼容 AutoJS6 / Rhino ES5.1。

## 验证与交付

覆盖原生请求/响应、设备认证、超时和错误脱敏、密钥加密/掩码、热更新关闭、评分归一化、行业模板、失败时不回退、仅决策采集和生成模型分离。完成设备、后端、前端回归与构建。使用用户提供的凭据进行一次合成输入连通性验证（若运行环境允许访问），不提交密钥或真实业务数据。更新现有草稿 PR #2；不自动合并或部署。

## 协议来源

- https://vercel.com/docs/ai-gateway/sdks-and-apis/typesafe
- https://docs.typesafe.ai/api/system-one
- https://docs.typesafe.ai/primitives/score
- https://docs.typesafe.ai/confidence
