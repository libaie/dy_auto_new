# dy_auto 数据库表结构

> 生成日期: 2026-05-14 | 数据库: SQLite (WAL mode) | 来源: server/app/db_models.py

---

## 1. accounts — 抖音账号

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| nickname | String(100) | NOT NULL | 账号昵称 |
| douyin_id | String(100) | NOT NULL | 抖音数字 ID |
| group | String(50) | NOT NULL, default="default" | 分组标识 |
| status | String(20) | NOT NULL, default="active" | active / risk_controlled / banned |
| cookie | Text | NULLABLE | 加密后的 Cookie |
| daily_limits | JSON | NOT NULL | 日操作上限 {likes,comments,follows,dms,replies,nurture_likes} |
| created_at | DateTime | NOT NULL | 创建时间 (北京时间) |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 2. devices — 设备

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | NOT NULL | 设备名称 |
| ip | String(50) | NULLABLE | IP 地址 |
| status | String(20) | NOT NULL, default="offline" | online / offline / maintenance |
| device_secret | String(64) | UNIQUE | 配对密钥 (SHA256) |
| bound_account_id | String(36) | FK→accounts.id | 绑定的账号 |
| proxy_config | JSON | NULLABLE | {type,host,port,username,password} |
| os_version | String(50) | NULLABLE | 系统版本 |
| app_version | String(20) | NULLABLE | 抖音 APP 版本 |
| screen_resolution | String(30) | NULLABLE | 屏幕分辨率 "1080x2400" |
| sdk_version | String(20) | NULLABLE | Android SDK 版本 |
| total_memory | Integer | NULLABLE | 总内存 (bytes) |
| manufacturer | String(50) | NULLABLE | 制造商 "samsung" |
| product | String(50) | NULLABLE | 产品代号 |
| device_model | String(50) | NULLABLE | 设备型号 |
| hardware | String(50) | NULLABLE | 硬件平台 |
| display | String(100) | NULLABLE | 显示器信息 |
| last_seen_at | DateTime | NULLABLE | 最后在线时间 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 3. device_pair_requests — 设备配对请求

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| pairing_token | String(64) | UNIQUE, INDEX | 配对令牌 |
| device_id | String(36) | NOT NULL | 设备自报 ID |
| device_name | String(100) | NOT NULL | 设备型号名 |
| os_version | String(50) | NULLABLE | 系统版本 |
| app_version | String(20) | NULLABLE | 抖音版本 |
| screen_resolution | String(30) | NULLABLE | 屏幕分辨率 |
| sdk_version | String(20) | NULLABLE | SDK 版本 |
| total_memory | Integer | NULLABLE | 总内存 |
| manufacturer | String(50) | NULLABLE | 制造商 |
| product | String(50) | NULLABLE | 产品代号 |
| device_model | String(50) | NULLABLE | 设备型号 |
| hardware | String(50) | NULLABLE | 硬件 |
| display | String(100) | NULLABLE | 显示器 |
| status | String(20) | NOT NULL, default="pending" | pending / approved / rejected |
| device_secret | String(64) | NULLABLE | 审批后生成的设备密钥 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 4. tasks — 任务

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| type | String(30) | NOT NULL | 类型: nurture / search_comment / search_like / search_dm / reply_comment / collect |
| account_id | String(36) | FK→accounts.id, NOT NULL | 执行账号 |
| device_id | String(36) | FK→devices.id | 执行设备 |
| params | JSON | NOT NULL | 任务参数 |
| status | String(20) | NOT NULL, default="pending" | pending / running / completed / failed / cancelled |
| result | JSON | NULLABLE | 执行结果 |
| retry_count | Integer | NOT NULL, default=0 | 重试次数 |
| scheduled_at | DateTime | NULLABLE | 计划执行时间 |
| started_at | DateTime | NULLABLE | 开始执行时间 |
| completed_at | DateTime | NULLABLE | 完成时间 |
| chain_instance_id | String(36) | FK→chain_instances.id | 所属链路实例 |
| step_order | Integer | NULLABLE | 在链路中的步骤序号 |

---

## 5. ui_selectors — UI 选择器

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| action_name | String(100) | INDEX, NOT NULL | 动作名 "video_comment_btn" |
| description | String(200) | NOT NULL | 描述 |
| platform_version | String(50) | NOT NULL, default="default" | 目标平台版本 "38.7.0" |
| strategies | JSON | NOT NULL | 查找策略 [{type,value,priority,...}] |
| version | Integer | NOT NULL, default=1 | 选择器版本号 |
| enabled | Boolean | NOT NULL, default=True | 是否启用 |
| category | String(50) | INDEX | 分类 comment/user/search |
| purpose | String(20) | NOT NULL, default="locate" | locate / extract |
| extract_field | String(20) | NULLABLE | 提取字段: text/desc/id/className |
| clean_mode | String(20) | NULLABLE | 清洗模式: raw/regex/ai |
| clean_pattern | Text | NULLABLE | 正则清洗模板 |
| clean_prompt | Text | NULLABLE | AI 清洗提示词 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 6. daily_stats — 日统计

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| account_id | String(36) | FK→accounts.id, INDEX, NOT NULL | 账号 |
| date | String(10) | INDEX, NOT NULL | 日期 YYYY-MM-DD |
| likes | Integer | NOT NULL, default=0 | 点赞数 |
| comments | Integer | NOT NULL, default=0 | 评论数 |
| follows | Integer | NOT NULL, default=0 | 关注数 |
| dms | Integer | NOT NULL, default=0 | 私信数 |
| replies | Integer | NOT NULL, default=0 | 回复数 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

**唯一约束**: (account_id, date)

---

## 7. content_templates — 内容模板

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | NOT NULL | 模板名称 |
| category | String(50) | NOT NULL, default="comment" | comment / dm / reply |
| body | Text | NOT NULL | 模板正文 |
| variables | JSON | NOT NULL | 变量列表 ["keyword","username"] |
| is_active | Boolean | NOT NULL, default=True | 是否启用 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 8. sensitive_words — 敏感词库

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| word | String(100) | UNIQUE, NOT NULL | 敏感词 |
| created_at | DateTime | NOT NULL | 创建时间 |

---

## 9. account_groups — 账号分组

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | UNIQUE, NOT NULL | 分组名称 |
| description | String(500) | NULLABLE | 描述 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 10. account_group_members — 分组-账号关联

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| group_id | String(36) | FK→account_groups.id, CASCADE | 分组 |
| account_id | String(36) | FK→accounts.id, CASCADE | 账号 |
| created_at | DateTime | NOT NULL | 创建时间 |

**唯一约束**: (group_id, account_id)

---

## 11. chain_templates — 任务链模板

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | NOT NULL | 模板名称 |
| description | String(500) | NULLABLE | 描述 |
| steps | JSON | NOT NULL | [{step_order,type,label,params}] |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 12. chain_instances — 任务链实例

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| template_id | String(36) | FK→chain_templates.id, RESTRICT | 所属模板 |
| account_id | String(36) | FK→accounts.id, RESTRICT | 执行账号 |
| device_id | String(36) | FK→devices.id | 执行设备 |
| current_step | Integer | NOT NULL, default=1 | 当前步骤 |
| total_steps | Integer | NOT NULL | 总步骤数 |
| status | String(20) | NOT NULL, default="pending" | pending/running/completed/failed/cancelled |
| created_at | DateTime | NOT NULL | 创建时间 |
| started_at | DateTime | NULLABLE | 开始时间 |
| completed_at | DateTime | NULLABLE | 完成时间 |

---

## 13. replied_comments — 已回复评论去重

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| content_hash | String(64) | PK | SHA256(author+text) |
| author | String(200) | NOT NULL | 评论作者 |
| text | Text | NOT NULL | 评论内容 |
| replied_by_device | String(36) | NULLABLE | 回复设备 ID |
| created_at | DateTime | NOT NULL | 创建时间 |

---

## 14. system_settings — 系统设置

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| key | String(100) | PK | 设置键 |
| value | Text | NOT NULL | 设置值 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 15. channels — 频道（关键词任务队列）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| group_id | String(36) | FK→account_groups.id, RESTRICT | 账号分组 |
| task_type | String(30) | NOT NULL | 任务类型 |
| status | String(20) | NOT NULL, default="active" | active/paused/completed/cancelled |
| account_mode | String(20) | NOT NULL, default="round_robin" | single_account / round_robin |
| account_id | String(36) | FK→accounts.id | 单账号模式指定账号 |
| params_template | JSON | NOT NULL | 任务参数模板 |
| cooldown_seconds | Integer | NOT NULL, default=300 | 冷却时间 (秒) |
| delay_range | JSON | NOT NULL | 延迟范围 [min_ms, max_ms] |
| max_keywords | Integer | NOT NULL, default=500 | 最大关键词数 |
| current_account_index | Integer | NOT NULL, default=0 | 轮询账号索引 |
| created_at | DateTime | NOT NULL | 创建时间 |
| completed_at | DateTime | NULLABLE | 完成时间 |
| deleted_at | DateTime | NULLABLE | 软删除时间 |

---

## 16. channel_items — 频道关键词条目

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| channel_id | String(36) | FK→channels.id, CASCADE | 所属频道 |
| keyword | String(200) | NOT NULL | 关键词 |
| account_id | String(36) | FK→accounts.id | 分配账号 |
| status | String(20) | NOT NULL, default="pending" | pending/assigned/completed/failed/skipped |
| assigned_device_id | String(36) | FK→devices.id | 分配设备 |
| assigned_at | DateTime | NULLABLE | 分配时间 |
| task_id | String(36) | FK→tasks.id | 关联任务 |
| queue_position | Integer | NOT NULL, default=0 | 队列位置 |
| created_at | DateTime | NOT NULL | 创建时间 |
| completed_at | DateTime | NULLABLE | 完成时间 |

**索引**: (channel_id, status)

---

## 17. prompt_templates — AI 提示词模板

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | UNIQUE, INDEX, NOT NULL | 模板名称 |
| industry | String(50) | INDEX, NOT NULL, default="health" | 行业 health/travel |
| description | String(200) | NOT NULL | 描述 |
| content | JSON | NOT NULL | {identity, semanticGuide, analysis,...} |
| version | Integer | NOT NULL, default=1 | 版本号 |
| enabled | Boolean | NOT NULL, default=True | 是否启用 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 18. collected_comments — 采集的评论

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| task_id | String(36) | FK→tasks.id, INDEX | 关联任务 |
| device_id | String(36) | FK→devices.id | 采集设备 |
| keyword | String(200) | NOT NULL | 搜索关键词 |
| nickname | String(100) | NOT NULL | 评论者昵称 |
| content | Text | NOT NULL | 评论内容 |
| time_str | String(50) | NULLABLE | 评论发布时间 |
| reply_count | String(20) | NULLABLE | 回复数 |
| like_count | String(20) | NULLABLE | 点赞数 |
| dislike_count | String(20) | NULLABLE | 踩数 |
| location | String(100) | NULLABLE | IP 属地 |
| is_author | Boolean | NOT NULL, default=False | 是否作者 |
| ai_reply | Text | NULLABLE | AI 生成的回复 |
| ai_replied_at | DateTime | NULLABLE | AI 回复时间 |
| created_at | DateTime | NOT NULL | 采集时间 (北京时间) |

---

## 19. collected_users — 采集的用户

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| task_id | String(36) | FK→tasks.id, INDEX | 关联任务 |
| device_id | String(36) | FK→devices.id | 采集设备 |
| nickname | String(100) | NOT NULL | 用户昵称 |
| douyin_id | String(100) | **UNIQUE, INDEX**, NOT NULL | 抖音数字 ID (去重键) |
| keyword | String(200) | INDEX | 采集关键词/行业 |
| likes_count | String(20) | NULLABLE | 获赞数 |
| follow_count | String(20) | NULLABLE | 关注数 |
| fans_count | String(20) | NULLABLE | 粉丝数 |
| works_count | String(20) | NULLABLE | 作品数 |
| gender | String(10) | NULLABLE | 性别 |
| age | String(10) | NULLABLE | 年龄 |
| ip_location | String(100) | NULLABLE | IP 属地 |
| is_private | String(10) | NULLABLE | 是否私密账号 |
| avatar_url | Text | NULLABLE | 头像路径 /api/device/avatar/{douyin_id} |
| created_at | DateTime | NOT NULL | 首次采集时间 |

> **Upsert**: douyin_id 唯一键，已存在则更新除 douyin_id 外全部字段。

---

## 20. conversations — 私信会话

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| task_id | String(36) | FK→tasks.id, INDEX | 关联任务 |
| account_id | String(36) | FK→accounts.id, INDEX, NOT NULL | 我方账号 |
| device_id | String(36) | FK→devices.id | 执行设备 |
| keyword | String(200) | NULLABLE | 搜索关键词 |
| recipient_nickname | String(100) | NOT NULL | 对方昵称 |
| recipient_douyin_id | String(100) | NOT NULL | 对方抖音 ID |
| current_stage | String(20) | INDEX, NOT NULL, default="qualifying" | qualifying/nurturing/converting/follow_up |
| intent | String(30) | NULLABLE | AI 判定意图 |
| last_dm_content | Text | NULLABLE | 最后私信内容 |
| last_dm_at | DateTime | NULLABLE | 最后私信时间 |
| claimed_at | DateTime | NULLABLE | 占用时间 (防多设备冲突) |
| status | String(20) | INDEX, NOT NULL, default="active" | active/replied/closed |
| total_dm_count | Integer | NOT NULL, default=0 | 总私信条数 |
| reply_received_at | DateTime | NULLABLE | 对方回复时间 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

**唯一约束**: (account_id, recipient_douyin_id)

---

## 21. generated_videos — AI 生成视频

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| task_id | String(36) | FK→tasks.id | 关联任务 |
| keyword | String(200) | NOT NULL | 关键词 |
| title | String(500) | NULLABLE | 标题 |
| video_path | String(500) | NULLABLE | 文件路径 |
| duration | Float | NULLABLE | 时长 (秒) |
| status | String(20) | NOT NULL, default="pending" | pending/generating/completed/failed |
| pixelle_task_id | String(100) | NULLABLE | Pixelle-Video 任务 ID |
| error | Text | NULLABLE | 错误信息 |
| created_at | DateTime | NOT NULL | 创建时间 |

---

## 22. characters — 角色

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | NOT NULL | 角色名 |
| role_type | String(20) | NOT NULL, default="protagonist" | protagonist/antagonist/supporting |
| gender | String(10) | NOT NULL, default="male" | male/female |
| age_range | String(20) | NULLABLE | 年龄段 |
| personality | Text | NULLABLE | 性格描述 |
| appearance_desc | Text | NULLABLE | 外貌描述 |
| outfit_desc | Text | NULLABLE | 服装描述 |
| avatar_front_url | Text | NULLABLE | 正面头像 |
| avatar_side_url | Text | NULLABLE | 侧面头像 |
| avatar_threequarter_url | Text | NULLABLE | 3/4 侧面 |
| avatar_fullbody_url | Text | NULLABLE | 全身像 |
| default_voice_id | String(100) | NULLABLE | 默认 TTS 语音 |
| meta_json | JSON | NULLABLE | 扩展元数据 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 23. scenes — 场景

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| name | String(100) | NOT NULL | 场景名 |
| scene_type | String(20) | NOT NULL, default="indoor" | indoor/outdoor |
| location_desc | Text | NULLABLE | 地点描述 |
| lighting | String(50) | NULLABLE | 光照 |
| mood | String(50) | NULLABLE | 氛围 |
| reference_wideshot_url | Text | NULLABLE | 广角参考图 |
| reference_midshot_url | Text | NULLABLE | 中景参考图 |
| reference_aerial_url | Text | NULLABLE | 航拍参考图 |
| meta_json | JSON | NULLABLE | 扩展元数据 |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

---

## 24. series — 系列（短剧）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| title | String(200) | NOT NULL | 剧名 |
| logline | Text | NULLABLE | 一句话梗概 |
| genre | String(50) | NOT NULL, default="drama" | 类型 |
| total_episodes | Integer | NOT NULL, default=30 | 总集数 |
| target_duration | Integer | NOT NULL, default=90 | 目标时长 (秒/集) |
| mode | String(20) | NOT NULL, default="step_by_step" | 生成模式 |
| pilot_first | Boolean | NOT NULL, default=True | 是否先导 Pilot |
| story_bible_json | JSON | NULLABLE | 故事圣经 |
| status | String(20) | NOT NULL, default="draft" | draft/generating/completed |
| created_at | DateTime | NOT NULL | 创建时间 |
| updated_at | DateTime | NOT NULL | 更新时间 (自动) |

**M2M**: characters (series_characters), scenes (series_scenes)

---

## 25. episodes — 剧集

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| series_id | String(36) | FK→series.id, CASCADE | 所属系列 |
| episode_number | Integer | NOT NULL | 集号 |
| title | String(200) | NULLABLE | 分集标题 |
| script_json | JSON | NULLABLE | 剧本 |
| storyboard_json | JSON | NULLABLE | 分镜 |
| video_url | Text | NULLABLE | 成品视频 URL |
| duration_seconds | Integer | NULLABLE | 时长 (秒) |
| status | String(20) | NOT NULL, default="pending" | pending/script/storyboard/rendering/completed/failed |
| cost_so_far | Float | NULLABLE, default=0.0 | 累计成本 |
| created_at | DateTime | NOT NULL | 创建时间 |

**唯一约束**: (series_id, episode_number)

---

## 26. pipeline_runs — 流水线运行记录

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| series_id | String(36) | FK→series.id, CASCADE | 所属系列 |
| episode_id | String(36) | FK→episodes.id, SET NULL | 关联剧集 |
| mode | String(20) | NOT NULL, default="step_by_step" | 运行模式 |
| layers_json | JSON | NULLABLE | 各层状态 {0-5: {status,result}} |
| current_layer | Integer | NOT NULL, default=0 | 当前执行层 |
| status | String(20) | NOT NULL, default="pending" | pending/running/completed/failed |
| error_log | Text | NULLABLE | 错误日志 |
| actual_cost_so_far | Float | NULLABLE, default=0.0 | 实际累计成本 |
| started_at | DateTime | NULLABLE | 开始时间 |
| completed_at | DateTime | NULLABLE | 完成时间 |
| created_at | DateTime | NOT NULL | 创建时间 |

**索引**: (series_id)

---

## 27. audit_reports — AI 审核报告

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| target_type | String(20) | NOT NULL | 审核目标类型 |
| target_id | String(36) | NOT NULL | 审核目标 ID |
| image_url | Text | NOT NULL | 审核图片 URL |
| auditor_model | String(50) | NOT NULL | 审核模型 gpt-4o |
| score | Float | NOT NULL, default=0.0 | 评分 |
| pass_fail | Boolean | NOT NULL, default=False | 是否通过 |
| issues_json | JSON | NULLABLE | 问题列表 |
| raw_response | Text | NULLABLE | 原始 AI 返回 |
| created_at | DateTime | NOT NULL | 创建时间 |

---

## 28. reference_data — 系统字典

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | String(36) | PK, UUID | 主键 |
| category | String(50) | INDEX, NOT NULL | series_genre/character_role/scene_type/scene_lighting/scene_mood |
| value | String(100) | NOT NULL | 值 (机器可读) |
| label | String(100) | NOT NULL | 显示名 (可中文) |
| sort_order | Integer | NOT NULL, default=0 | 排序 |
| enabled | Boolean | NOT NULL, default=True | 是否启用 |
| created_at | DateTime | NOT NULL | 创建时间 |

**唯一约束**: (category, value)

---

## 关联关系

```
accounts ──┬── tasks ──┬── chain_instances ─── chain_templates
           │           ├── channel_items ─── channels ─── account_groups ──┬── account_group_members
           │           ├── collected_comments                              │
           │           ├── collected_users                                 │
           │           ├── conversations                                    │
           │           └── generated_videos                                 │
           │                                                               │
           ├── daily_stats                                                │
           └── account_group_members                                       │
                                                                          │
devices ──┬── tasks                                                       │
          ├── device_pair_requests                                         │
          ├── chain_instances                                              │
          ├── channel_items                                                │
          ├── collected_comments                                           │
          ├── collected_users                                              │
          └── conversations                                                │
                                                                          │
series ──┬── episodes ─── pipeline_runs                                   │
         ├── series_characters ── characters                               │
         └── series_scenes ── scenes                                       │
```

## 独立表（无外键依赖）

ui_selectors | content_templates | sensitive_words | system_settings | prompt_templates | replied_comments | reference_data

---

**总计: 28 张表 + 2 张 M2M 中间表 (series_characters, series_scenes)**
