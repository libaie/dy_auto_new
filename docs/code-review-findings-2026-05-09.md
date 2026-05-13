# dy_auto 项目深度代码审查报告

审查日期：2026-05-09  
范围：后端 FastAPI、设备端 Auto.js 脚本、前端 Vue 管理端、数据库迁移与测试  
要求：只找问题，不做修复

## 总览

本次审查共发现 10 个问题：

| 优先级 | 数量 | 说明 |
| --- | ---: | --- |
| P0 | 1 | 可导致凭据泄露或严重安全事故 |
| P1 | 4 | 高风险安全、任务归属或重复执行问题 |
| P2 | 5 | 中风险正确性、稳定性、部署或测试缺口 |

验证结果：

- `python -m compileall -q server/app`：通过
- 设备端 JS `node --check`：通过
- 前端 `npm run build`：通过
- 后端 `pytest`：308 passed / 22 failed
- 后端测试失败集中在 AI 生成器测试、任务参数校验、内容模板解析行为

## 问题清单

### 1. [P0] 未鉴权配对接口会泄露已有设备 secret

位置：`server/app/routers/device.py:102-120`

`/api/device/pair-request` 只要提交一个已存在且已配对的 `device_id`，就会直接返回该设备的 `device_secret` 和配置。知道或猜到设备 ID 的请求方可以拿到设备凭据，后续轮询任务、上报结果、调用设备侧接口。

影响：

- 攻击者可伪装成已配对设备。
- 可读取/领取任务，污染执行结果。
- 可调用设备侧 AI、模板、脚本下载等接口。

### 2. [P1] 默认生产凭据可直接启用

位置：`server/app/config.py:21-26`

`DEVICE_SECRET`、`ADMIN_PASSWORD`、`JWT_SECRET` 都有硬编码默认值，启动时只是打印 warning。未配置环境变量时，管理端和设备端鉴权都会落到公开默认凭据上。

影响：

- 新环境或误配置环境可被默认账号密码登录。
- 默认 `JWT_SECRET` 会让 JWT 可被伪造。
- 默认 `DEVICE_SECRET` 等价于全局设备主密钥泄露。

### 3. [P1] 设备结果上报的任务归属校验不完整

位置：`server/app/routers/device.py:458-465`

`/api/device/report` 只有在 `db_task.device_id` 已存在时才拒绝其他设备；未绑定设备的 pending/running 任务可被任意已配对设备按任务 ID 上报完成或失败。

影响：

- 设备间可以越权提交任务结果。
- 任务状态、统计数据、通道进度可能被污染。
- 任务 ID 一旦泄露或被猜到，结果可信度会下降。

### 4. [P1] 通道任务可被未绑定设备抢走绑定账号的任务

位置：`server/app/services/channel_service.py:161-172`

普通任务路径会排除已绑定到其他设备的账号，但通道 claim 逻辑只在当前设备已绑定时过滤账号；未绑定设备会看到所有 pending channel item，可能执行本该由绑定设备处理的账号任务。

影响：

- 账号与设备绑定规则不一致。
- 绑定账号任务可能在错误设备上执行。
- 代理、风控、登录态隔离可能失效。

### 5. [P1] 固定 3 分钟回收运行中任务会导致重复执行

位置：`server/app/services/task_service.py:104-124`

`get_pending_task` 会把所有 started 超过 3 分钟的 RUNNING 任务直接重置为 PENDING，并同步释放 channel item。长耗时任务或设备仍在正常执行时，其他设备可能再次领取并产生重复点赞、评论、私信等副作用。

影响：

- 长任务可能被重复执行。
- 评论、点赞、私信等外部副作用无法回滚。
- 通道进度和每日限额统计可能失真。

### 6. [P2] 任务参数校验模型没有接入创建接口

位置：`server/app/routers/tasks.py:20-31`

`TaskCreateRequest.params` 和批量创建的 `params` 都只是裸 dict，创建任务时直接入库，`models.py` 中的 `TASK_PARAMS_VALIDATORS` 没被调用。测试也验证了空 `sub_tasks`、非法类型、超限 count/duration 都被 200 接受。

影响：

- 无效任务参数进入队列。
- 设备端执行时才失败，问题发现延迟。
- API 契约与模型定义不一致。

### 7. [P2] content_template_id 创建任务时不会解析成 content

位置：`server/app/routers/tasks.py:70-78`

创建任务只经过 `_maybe_expand_keywords`，然后直接 `task_service.create_task`。带 `content_template_id` 的 search/comment/dm 任务不会注入生成内容，设备端读取 `params.content || ''`，实际可能空内容执行。

影响：

- 任务看似使用了内容模板，但设备端拿不到生成内容。
- 评论、私信、回复类任务可能发送空内容或执行失败。
- 现有测试中 `test_create_task_with_template_resolves_content` 已失败。

### 8. [P2] WebSocket secret 放在 URL 且被日志打印

位置：`device/core/device-ws.js:147-152`

设备状态 WS 把 `deviceSecret` 放在 query string，随后完整打印 `wsUrl`。URL 常被代理、服务端、客户端日志记录，等价于把设备长期凭据写入日志。

影响：

- 设备 secret 可能进入日志系统。
- 日志访问者可复用 secret 伪装设备。
- URL 凭据也更容易被代理、抓包、异常报告泄露。

### 9. [P2] 登录限流信任客户端可伪造的转发头

位置：`server/app/routers/auth.py:23-31`

登录限流直接使用 `X-Forwarded-For` 或 `X-Real-IP` 的首个值作为客户端 IP。如果服务直接暴露或代理未清洗这些头，攻击者可换头绕过 5 次失败限制。

影响：

- 登录爆破保护可被绕过。
- 默认凭据风险会被进一步放大。
- 限流统计不可信。

### 10. [P2] Alembic 迁移与 ORM 模型严重漂移

位置：`server/alembic/versions/3145b6441241_initial_schema.py:21-77`

初始迁移只创建 accounts、ui_selectors、devices、tasks 等少量表，当前 ORM 已包含 channels、prompt_templates、content、stats、collect 等多张表和大量新列。依赖 Alembic 部署的新环境会缺表/缺列，运行时 `create_all` 掩盖了迁移缺口。

影响：

- 使用 Alembic 初始化的新环境无法得到完整 schema。
- 线上迁移、回滚和审计链路不可靠。
- `create_all` 与手写 `_migrate_add_columns` 会让真实数据库状态难以追踪。

## 测试失败摘要

后端测试当前结果为 `308 passed / 22 failed`。失败方向如下：

- `tests/test_ai_generator.py`：AI 生成器测试与当前实现接口不一致，例如测试仍 patch `AI_API_KEY`、`AI_PROVIDER` 模块变量，但实现已改为从 `get_ai_config_with_key(db)` 解析配置。
- `tests/test_content_service.py`：内容生成模板测试仍依赖旧配置 patch 路径。
- `tests/test_tasks_api.py` 与 `tests/test_integration.py`：任务参数校验未接入创建接口，导致无效 Nurture V2 参数返回 200；`content_template_id` 未解析成 `content`。

## 建议处理顺序

1. 先处理 P0 配对 secret 泄露，避免已配对设备凭据被任意取回。
2. 处理默认凭据与设备 report 越权，补齐最基础的信任边界。
3. 修正通道 claim 路由与运行中任务回收策略，避免错误设备执行和重复副作用。
4. 接入任务参数校验与内容模板解析，恢复 API 契约和测试预期。
5. 统一凭据传递方式、登录限流可信 IP 策略和 Alembic 迁移链路。
