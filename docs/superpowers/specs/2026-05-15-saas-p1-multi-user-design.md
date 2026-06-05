# dy_auto SaaS P1 — 多用户认证 + 数据隔离 + 设备登录绑定

> 设计文档 · 2026-05-15 · Status: proposed

**目标:** 将 dy_auto 从单管理员实例改造为支持多用户、角色区分、数据隔离的 SaaS-ready 系统。设备端通过账号密码登录绑定用户。

**范围:** P1 聚焦核心改造（认证 + 隔离 + 角色），不含 SaaS 平台门户和计费（P2/P3）。

---

## 架构概览

```
┌─────────────┐     POST /api/auth/login      ┌──────────────────┐
│   Web 前端   │ ────────────────────────────── │   FastAPI Server  │
│  (Vue SPA)  │     JWT {sub,user_id,role}     │                  │
└─────────────┘                                 │  ┌────────────┐  │
                                                │  │ deps.py    │  │
┌─────────────┐   POST /api/auth/device-login   │  │ verify_*   │  │
│  设备端      │ ────────────────────────────── │  └────────────┘  │
│ (AutoJS6)   │     JWT → X-Device-Secret       │                  │
│             │     后续请求带 X-Device-Secret    │  ┌────────────┐  │
│             │                                 │  │ 路由层 24 个│  │
│             │                                 │  │ 全加 user   │  │
│             │                                 │  │ scope 过滤  │  │
└─────────────┘                                 └──────────────────┘
```

---

## 1. 数据模型

### 1.1 新增：users 表

```python
class User(Base):
    __tablename__ = "users"

    id            = Column(String(36), PK, default=uuid)
    username      = Column(String(50), unique, NOT NULL, index)
    password_hash = Column(String(128), NOT NULL)          # bcrypt
    role          = Column(String(20), default="operator")  # admin | operator
    nickname      = Column(String(100), nullable=True)
    status        = Column(String(20), default="active")    # active | disabled
    created_at    = Column(DateTime, default=bj_now)
    updated_at    = Column(DateTime, default=bj_now, onupdate=bj_now)
```

**初始化 admin:** 首次启动时检查 users 表，若为空则用 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 环境变量创建默认 admin 用户。之后 env var 仅作为 fallback seed，不参与日常登录。

### 1.2 需要加 user_id 的表

| 表 | 改动 | 说明 |
|----|------|------|
| `devices` | `user_id FK → users.id, nullable` | 设备归属，pair 审批时赋值 |
| `accounts` | `user_id FK → users.id, nullable` | 抖音账号归属 |
| `account_groups` | `user_id FK → users.id, nullable` | 账号分组归属 |
| `tasks` | `user_id FK → users.id, nullable` | 任务归属 |
| `channels` | `user_id FK → users.id, nullable` | 通道归属 |
| `chain_templates` | `user_id FK → users.id, nullable` | 链模板归属 |
| `chain_instances` | `user_id FK → users.id, nullable` | 链实例归属 |

### 1.3 无需 user_id 的表（全局共享）

| 表 | 原因 |
|----|------|
| `reference_data` | 系统字典，所有用户共用 |
| `prompt_templates` | AI 模板，实例级共享 |
| `content_templates` | 内容模板，实例级共享 |
| `ui_selectors` | UI 选择器配置，实例级共享 |
| `system_settings` | 系统配置，实例级共享 |
| `collected_comments` | 已有 task_id → 通过 task 链路关联 user |
| `collected_users` | 同上 |
| `conversations` | 同上 |

### 1.4 共享表的 user_id 策略

`collected_*` 和 `conversations` 表不直接加 `user_id`。数据归属通过 `task_id` 链路推导：

```python
# 查询时 JOIN 过滤
query = db.query(CollectedComment).join(Task, CollectedComment.task_id == Task.id)
query = query.filter(Task.user_id == current_user_id)
```

### 1.5 Migration 策略

Alembic migration:

1. 创建 `users` 表
2. 在 7 张业务表加 `user_id` 列（全部 `nullable=True`，不做数据回填）
3. 用 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 创建默认 admin 用户
4. 现有数据的 `user_id` 留 NULL — admin 用户查询时 `user_id IS NULL OR user_id = ?` 兼容过渡期

**升级后行为:** admin 用户能看到所有历史数据（包括 user_id=NULL 的），operator 用户只能看到显式绑定到自己 ID 的数据。

---

## 2. 认证改造

### 2.1 deps.py — 依赖注入链

```python
# 当前
def verify_admin_token(...) -> str:       # 返回 username
    ...

# 目标
def verify_admin_token(...) -> tuple[str, str]:  # 返回 (user_id, role)
    ...

def require_role(*roles: str):
    """工厂函数，返回检查角色的 FastAPI 依赖"""
    async def checker(user=Depends(verify_admin_token)):
        user_id, role = user
        if role not in roles:
            raise HTTPException(403, "权限不足")
        return user
    return checker

def get_current_user_id(user=Depends(verify_admin_token)) -> str:
    """仅返回 user_id，用于数据过滤"""
    return user[0]
```

### 2.2 JWT 载荷

```python
# 当前
{"sub": "admin", "exp": ..., "iat": ...}

# 目标
{"sub": "admin", "user_id": "uuid", "role": "admin", "exp": ..., "iat": ...}
```

### 2.3 auth.py — 登录改造

`POST /api/auth/login`:
- 当前: `hmac.compare_digest(password, ADMIN_PASSWORD)`
- 目标: 查 users 表 → `bcrypt.verify(password, user.password_hash)` → 签发含 `user_id` + `role` 的 JWT

新增 `POST /api/auth/device-login`:
- 设备发 `{username, password}`
- 验证后返回 `{device_secret, user_id}`（设备保存 secret，后续请求沿用 X-Device-Secret 头）
- 若该设备尚无 device_secret，自动生成并绑定到当前 user

新增 `POST /api/auth/register`（仅 admin 可调用）:
- 创建新用户，默认 role=operator

### 2.4 前端 — auth store 改造

```javascript
// 当前
{ token, username }

// 目标
{ token, username, userId, role }
```

- router guard 根据 role 控制页面可见性
- operator 看不到设备管理、账号管理、系统设置等管理页面
- LoginPage 不变（仍用同一登录接口）

---

## 3. 数据隔离

### 3.1 路由层改造模式

每条查询加 user scope 过滤。分三类：

**模式 A — 全局共享表:** 不加过滤（reference_data, prompt_templates 等）

**模式 B — 带 user_id 的表:**
```python
# admin: 看全部
# operator: WHERE user_id = current_user_id
if role != "admin":
    query = query.filter(Model.user_id == current_user_id)
```

**模式 C — 通过 task_id 链路关联的表:**
```python
# collected_comments, collected_users, conversations
if role != "admin":
    query = query.join(Task, Model.task_id == Task.id)
    query = query.filter(Task.user_id == current_user_id)
```

### 3.2 创建资源时注入 user_id

所有 POST/PUT 创建资源的端点：
```python
new_record = Model(..., user_id=current_user_id)
```

operator 创建 task/channel/chain 时自动绑定自己的 user_id。admin 可选指定 user_id（跨用户创建）。

### 3.3 WebSocket 隔离

- `broadcast_to_admins()` 改为 `broadcast_to_user(user_id)` 或 `broadcast_to_all_admins()`
- 设备状态变更只推送给该设备所属用户
- admin 用户接收全局广播

---

## 4. 设备登录流程

### 4.1 当前流程 vs 目标流程

```
当前:                                           目标:
──────                                         ──────
设备端输入服务器 IP                              设备端输入服务器 IP + 账号密码
POST /api/device/pair-request                   POST /api/auth/device-login
等待 admin 审批                                 服务端验证 + 签发 device_secret
WS 推送 secret                                  保存 secret 到本地存储
后续请求带 X-Device-Secret                       后续请求带 X-Device-Secret（不变）
```

### 4.2 设备端改动

0 行代码改动。保持 `X-Device-Secret` 头不变。服务端 `verify_device_secret` 已能解析 `device_id`，通过 `Device.user_id` 关联到对应用户。

唯一新增：第一次登录获取 secret 时改用 `/api/auth/device-login` 而非 `pair-request`。

### 4.3 设备管理

- admin 可以在管理后台为设备分配 user（修改 devices.user_id）
- 一个用户可以有多个设备
- 设备解绑：清空 user_id，设备失联后可被其他用户认领

---

## 5. 角色权限矩阵

| 功能 | admin | operator |
|------|-------|----------|
| 仪表盘 | 全部数据 | 仅自己数据 |
| 任务管理 | CRUD 全部 | CRUD 自己 |
| 通道管理 | CRUD 全部 | CRUD 自己 |
| 数据采集列表 | 查看全部 | 查看自己 |
| 用户管理 | ✅ (CRUD) | ❌ |
| 设备管理 | ✅ | ❌ |
| 账号管理 | ✅ | ❌ |
| 账号分组 | ✅ | ❌ |
| 选择器/模板/字典 | ✅ | ❌ (只读部分) |
| AI 配置 | ✅ | ❌ |
| 系统设置 | ✅ | ❌ |
| 数据中心 | 查看全部 | 查看自己 |

---

## 6. 实现顺序

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | Alembic migration: users 表 + 7 张业务表加 user_id | 1 个 migration 文件 |
| 2 | deps.py: `verify_admin_token` 升级、`require_role`、`get_current_user_id` | deps.py |
| 3 | auth.py: 登录查 DB、新增 device-login、新增 register | auth.py |
| 4 | db_models.py: User 模型、user_id FKs | db_models.py |
| 5-20 | 各路由文件: 加 user scope 过滤 + 创建时注入 user_id | 24 个路由文件 |
| 21 | 前端 auth store + router guard 改造 | stores/auth.js, router/index.js |
| 22 | 前端用户管理页 + LoginPage 微调 | views/ |
| 23 | WebSocket 隔离改造 | ws_manager.py |
| 24 | device.py: pair-approval 绑定 user_id | device.py |

---

## 7. 风险与回滚

- **Migration 风险:** 所有新增列 `nullable=True`，不破坏现有数据。可安全回滚。
- **auth 兼容:** 首启动自动从 env var 创建 admin，现有登录凭据不变。
- **设备兼容:** 现有已配对设备不受影响（user_id=NULL，admin 可见）。
- **前端兼容:** token 仍存 localStorage，旧 token 失效后重登即可。
