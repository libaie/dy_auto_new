# AI 视频生成代码审查矩阵 - 2026-06-22

目标：逐项审查 AI 视频生成链路，记录每个功能点的代码入口、验证证据和未完全证明的风险。

## 当前结论

| 功能点 | 代码入口 | 证据 | 状态 |
| --- | --- | --- | --- |
| 一句话成片创建系列、占位剧集、首集分镜和生产 run | `server/app/domains/video_production/one_sentence_video_service.py` | `server/tests/test_one_sentence_video.py` | 已验证 |
| 一句话后续剧集不完全复用首集角色/场景 | `one_sentence_video_service._record_one_sentence_text_artifacts` | `test_one_sentence_video_creates_locked_storyboard_and_run` | 已验证 |
| 参考图超时/排队后恢复 | `complete_one_sentence_reference_generation` | `server/tests/test_one_sentence_video.py` | 已验证 |
| 系列故事规划、每集 outline、每集资产作用域 | `server/app/domains/ai_video_series/series_planning_service.py` | `server/tests/test_series_planning_service.py`, `server/tests/test_series_api.py` | 已验证 |
| 风格锁定与后台 worker | `server/app/domains/ai_video_series/style_lock.py`, `server/app/main.py` | `server/tests/test_series_style_lock_pipeline.py`, `server/tests/test_style_lock_background_worker.py` | 已验证 |
| 剧本/分镜文本产物列表、详情、编辑、审批、再生成 | `server/app/domains/ai_text_artifacts` | `server/tests/test_ai_text_artifacts_api.py` | 已验证 |
| AI 文本工作台前端路由和 API 客户端 | `web/src/router/index.js`, `web/src/api/aiTextArtifacts.js` | `web/src/__tests__/ai-text-artifact-workbench.test.js`, `web/src/__tests__/api-clients.test.js` | 已验证 |
| 启动单集生产、绑定文本产物、生成 production plan/tree | `server/app/domains/video_production/production_run_service.py` | `server/tests/test_video_production_start_flow_contract.py`, `server/tests/test_video_production_tree_api.py` | 已验证 |
| 图片、视频、合成阶段闸门 | `server/app/domains/video_production/video_production_service.py` | `server/tests/test_production_gate_evaluator.py`, `server/tests/test_video_production_state_machine.py` | 已验证 |
| LangChain provider tool 提交/查询编排 | `server/app/domains/ai_video_series/langchain_runtime` | `server/tests/test_ai_video_langchain_provider_tools.py`, `server/tests/test_ai_video_langchain_provider_stage_orchestrator.py` | 已验证 |
| 真实 worker 按 production_episode_id 隔离任务 | `server/app/domains/video_production/production_worker_service.py` | `server/tests/test_video_production_real_worker_step.py` | 已验证 |
| 后台真实 worker 生命周期 | `server/app/main.py` | `server/tests/test_device_operations_status_lifecycle.py`, `server/tests/test_style_lock_background_worker.py` | 已验证 |
| 专家审查阻塞不误记为失败 | `production_worker_service.py`, `agency_creative_patch_service.py` | `server/tests/test_video_production_creative_patch_gate.py`, `test_video_production_real_worker_step.py` | 已验证 |
| 分镜图任务、读取和提升到视频资产 | `server/app/domains/storyboard_images` | `server/tests/test_storyboard_images_api.py`, `server/tests/test_storyboard_image_service.py` | 已验证 |
| 视频审查、批量审批、void、image edit | `video_production_router.py`, `review_asset_edit_service.py` | `server/tests/test_video_production_api.py`, `web/src/__tests__/ai-video-review-page.test.js` | 已验证 |
| 资产重生成和 provider sync-regeneration | `video_production_service.sync_regenerated_asset` | `server/tests/test_video_production_api.py` | 已验证 |
| readiness、review-items、provider-stage-tasks、retry、pause/resume | `video_production_router.py`, read services | `server/tests/test_video_production_readiness.py`, `test_video_production_provider_stage_tasks_api.py`, `test_video_production_retry_impact.py`, `test_video_production_pause_resume.py` | 已验证 |
| 设置页敏感 provider key 脱敏 | `server/app/domains/system_configuration/settings_router.py` | `server/tests/test_settings_endpoints.py` | 已验证 |
| 真实 provider E2E 图像、视频、最终合成出片 | `server/scripts/smoke_bailian_one_sentence_e2e.py`, `server/app/domains/pixelle_integration/pixelle_stage_client.py` | 同一 `run_id=7a946c32-7362-461c-a45a-fc79bcf039da` 于 2026-06-23 恢复完成：百炼/DashScope 图片与视频阶段成功，`local_ffmpeg_compose` 合成终片 `e5afdb9b-43e6-4fc9-b075-a166292160e5.mp4`，run `completed` | 已验证 |

## 仍未完全证明

| 缺口 | 原因 | 最小下一步 |
| --- | --- | --- |
| 视觉模型免费额度轮换策略生产化 | 本轮按用户授权仅在本地测试配置中切换到有免费额度的百炼视觉模型，并在同一 smoke run 内验证完成；项目产品逻辑没有自动薅免费额度的 key/model fallback | 若要把多 key/多模型自动 fallback 产品化，需要单独设计配额策略、费用上限、审计日志和用户授权边界 |
| 非视频域外围代码 | AI 视频生成域、专家团队域、文本产物、分镜图、LangChain runtime、状态读模型、系列策划、风格锁定、前端核心页面、provider executor/router/readiness/队列/成本/审核/树/重试/存储支撑面已拆到函数组；采集/发布等非视频生成域不属于本轮“AI 视频生成代码”范围 | 若后续目标扩大到全仓库，再单独审查采集/发布域 |

## 函数级审查批次 A

文件：`server/app/domains/video_production/production_run_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 69-107 | `_style_lock`, `_production_episode_for_plan`, `segment_count_for_episode`, `create_linked_run` | run 与 production plan/episode 绑定，避免孤儿 run | `test_video_production_start_flow_contract.py`, `test_one_sentence_video_run_types.py` | 已验证 |
| 178-233 | `_assert_budget_allows_real_short_start`, `_target_duration_from_storyboard`, `_scale_frame_durations`, `_retime_storyboard_to_target` | real_short 时长和分镜重定时 | `test_video_production_start_flow_contract.py::test_start_flow_retimes_existing_storyboard_to_target_duration` | 已验证 |
| 266-419 | `_raise_if_latest_text_artifact_unapproved`, `_storyboard_*`, `_episode_script_from_storyboard`, `_create_approved_import_artifact`, `_ensure_episode_start_text_artifacts` | 剧本/分镜文本产物导入、审批闸门、消费绑定 | `test_video_production_start_flow_contract.py`, `test_ai_text_artifacts_api.py` | 已验证 |
| 534-636 | `_real_short_storyboard_needs_reference_rebuild`, `_dedupe_refs`, `_style_item_refs`, `_style_locked_reference_payload`, `_enrich_storyboard_with_style_refs`, `_compact_artifact_content` | real_short 参考图强校验和 style lock 参考图注入 | `test_video_production_start_flow_contract.py`, `test_one_sentence_video.py` | 已验证 |
| 655-789 | `_approved_story_context`, `_style_lock_name_maps`, `_series_asset_pool_summary`, `_usage_items`, `_episode_asset_scope_from_outline`, `_script_episode_asset_scope`, `_episode_asset_scope_for_production` | 每集角色/场景作用域来源，避免每集机械复用 | `test_series_planning_service.py`, `test_series_api.py`, `test_one_sentence_video.py` | 已验证 |
| 805-977 | `_scope_has_assets`, `_scope_needs_scene_mapping`, `_style_lock_ids`, `_series_asset_ids`, `_raise_episode_asset_scope_missing`, `_validate_episode_asset_scope_ids`, `_apply_episode_asset_scope_to_storyboard`, `_storyboard_has_frame_asset_scope`, `_ensure_episode_asset_scope_ready` | 资产 ID 合法性、多场景歧义阻断、分镜 frame scope 覆盖 | `test_video_production_start_flow_contract.py` | 已验证 |
| 988-1172 | `_script_gate_statuses`, `_raise_if_script_generation_blocked`, `_raise_if_existing_script_inputs_blocked`, `_episode_script_missing`, `_script_generation_source_prompt`, `_series_script_tags`, `_try_generate_script_storyboard`, `generate_episode_script_storyboard` | 剧本生成 gate、blocked trace、生成失败可修复错误 | `test_script_pipeline.py`, `test_video_production_start_flow_contract.py` | 已验证 |
| 1222-1276 | `_fallback_story_beat`, `_build_style_locked_storyboard` | 缺少持久分镜时的 style-lock fallback，不越过 episode scope gate | `test_video_production_start_flow_contract.py` | 已验证 |
| 1382-1407 | `_assert_real_short_duration`, `start_episode_production` | 单集生产总入口、预算、文本产物、分镜、plan、run 绑定 | `test_video_production_start_flow_contract.py`, `test_video_production_real_short_mocked_e2e.py` | 已验证 |

文件：`server/app/domains/video_production/video_production_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 73-174 | `VideoProductionError`, `_pixelle_output_root`, `_missing_agency_trace`, `_stage_context`, `_store_agency_trace`, `_blocked_status_for_agency_stage`, `_block_provider_stage` | provider 前专家审查 trace、blocked 状态落点 | `test_video_production_creative_patch_gate.py`, `test_production_gate_evaluator.py` | 已验证 |
| 174-312 | `_block_missing_provider_model_config`, `_block_regeneration_missing_provider_model_config`, `_run_agency_stage_review`, `_guard_provider_stage` | 缺模型配置阻断、专家审查超时/失败/通过分支 | `test_video_production_cost_safety.py`, `test_production_gate_evaluator.py` | 已验证 |
| 332-403 | `_frame_id`, `_next_asset_version`, `_next_asset_version_for_target`, `_demote_latest_assets`, `_is_linked_run` | 资产版本递增和 latest 降级 | `test_video_production_api.py`, `test_video_production_review_latest_version.py` | 已验证 |
| 416-568 | `_review_snapshot`, `_raise_stale_asset`, `_record_run_event`, `_assert_asset_persisted_for_review`, `_asset_is_persisted`, `_promote_linked_segment_for_approved_asset`, `_controlled_asset_url`, `_provider_input_asset_url`, `_stage_input_asset_url`, `persist_assets_for_review` | 审核快照、存储持久化、受控资产 URL | `test_video_production_api.py`, `test_image_asset_bridge.py`, `test_production_gate_evaluator.py` | 已验证 |
| 595-739 | `_force_review_status_after_blocked_gate`, `_raise_blocked_aggregate_gate`, `_guard_creative_patches`, `_assert_real_provider_path_run_type`, `_assert_real_short_provider_budget`, `_capability_from_runtime_model_config`, `_runtime_model_name`, `_assert_legacy_direct_stage_not_paid`, `_assert_regeneration_not_direct_paid_run`, `start_real_provider_stage_via_executor` | 真实 provider 边界、预算、付费直连禁用、creative patch gate | `test_video_production_cost_safety.py`, `test_video_production_creative_patch_gate.py`, `test_video_production_real_worker_step.py` | 已验证 |
| 829-1185 | `create_run_from_episode`, storyboard/image frame builders, `mark_image_stage_submitted`, `mark_image_stage_assets`, `start_image_stage` | run 创建、图片阶段输入、分镜图提升、图片任务提交和资产落库 | `test_video_production_mocked_e2e.py`, `test_video_production_real_short_mocked_e2e.py`, `test_storyboard_image_service.py` | 已验证 |
| 1237-1457 | `sync_image_stage_results`, AI 审核 helpers, `run_ai_audit_for_assets`, `latest_approved_assets_by_frame`, `approve_asset` | 图片同步、AI 审核、人工审批推进状态 | `test_video_production_full_mocked_e2e.py`, `test_video_production_review_latest_version.py`, `test_video_production_readiness.py` | 已验证 |
| 1510-1813 | `reject_asset`, video frame builders, `mark_video_stage_assets`, `start_video_stage`, `sync_video_stage_results` | 视频阶段依赖已审批图片、视频资产落库和状态推进 | `test_video_production_full_mocked_e2e.py`, `test_production_gate_evaluator.py`, `test_video_production_state_machine.py` | 已验证 |
| 1835-2001 | compose segment builders, `default_edit_manifest`, `compose_model_config`, `start_compose_stage` | 合成阶段输入、最终合成 provider 任务提交 | `test_video_production_real_short_mocked_e2e.py`, `test_production_gate_evaluator.py` | 已验证 |
| 2001-2320 | `_assert_final_asset_ready_for_writeback`, `complete_final_video`, final approve/reject/audit/persist/sync | 最终成片写回、最终人工审核、AI final audit 不自动完成 | `test_video_production_final_gate.py`, `test_video_production_full_mocked_e2e.py`, `test_video_production_ai_audit_gate.py`, `test_video_production_state_machine.py` | 已验证 |
| 2346-2500 | `start_asset_regeneration`, `_generated_or_old`, `sync_regenerated_asset`, `create_regenerated_image_asset` | 单资产重生成、provider sync、旧版本降级 | `test_video_production_api.py`, `test_video_production_mock_scale_api.py` | 已验证 |

文件：`server/app/domains/video_production/production_worker_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 64-178 | timeout/root helpers, `execute_real_job`, provider agent result helpers | provider agent 成功必须有 task 证据，blocked/error 统一转 `ProductionActionResult` | `test_video_production_real_worker_step.py`, `test_ai_video_langchain_provider_stage_orchestrator.py` | 已验证 |
| 178-329 | `execute_provider_job_direct`, `_run_deferred_stage_gates` | 直接 provider 执行、延迟专家 gate，不在 gate 阻塞时提交 provider | `test_video_production_creative_patch_gate.py`, `test_video_production_real_worker_step.py` | 已验证 |
| 329-523 | `run_real_worker_step`, `_claim_next_real_run_job`, unscoped/episode-scoped job queries, `_remaining_real_run_claimable_jobs` | real_short 只能抢当前 `production_episode_id` 范围任务；无 episode scope 时只允许 agency auto-repair | `test_video_production_real_worker_step.py`, `test_agency_repair_worker.py`, `test_agency_repair_loop.py` | 已验证 |
| 523-599 | `run_real_worker_queue_step`, model capability/cost helpers | 后台队列挑选 active real_short provider job，并允许 review/final-review 状态下的 scoped agency repair job；跳过无可领任务 run | `test_video_production_real_worker_step.py`, `test_style_lock_background_worker.py` | 已验证 |
| 599-820 | `_process_claimed_job`, `_run_async`, result helpers, `_record_blocked_result`, `_fail_or_reload_job`, `_failed_job_item` | leased/running/completed/blocked/failed 状态机；review gate blocked 不记 failed；failed job 响应项可追踪 | `test_video_production_real_worker_step.py`, `test_video_production_creative_patch_gate.py` | 已验证 |
| 820-891 | segment status helpers and provider task id extraction | job 状态回写到 segment，保留 provider task id | `test_video_production_real_worker_step.py` | 已验证 |
| 891-995 | model config, image reference support, text-only prompt/frame/storyboard transforms | 不支持参考图的图片模型降级为文本 prompt，不丢掉业务上下文 | `test_video_production_real_worker_step.py`, `test_ai_video_langchain_provider_tools.py` | 已验证 |
| 995-1169 | `_job_spec`, creative patch guard, frame lookup, provider payload template | 按 job target 组装 image/video/compose provider payload | `test_video_production_real_worker_step.py`, `test_video_production_real_short_mocked_e2e.py` | 已验证 |
| 1169-1274 | provider metadata compatibility, completed provider result persistence, asset persistence | 兼容 submit 函数签名，完成结果落库并触发审核 | `test_video_production_real_worker_step.py`, `test_video_production_real_short_mocked_e2e.py` | 已验证 |
| 1274-1370 | remaining/stage job queries and run status sync | stage open/failed/blocked 状态按当前 episode scope 汇总 | `test_video_production_real_worker_step.py` | 已验证 |

文件：`server/app/domains/video_production/one_sentence_video_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 84-206 | trace/reference/url helpers and blocked agency gate | agency trace、reference provider 错误脱敏、blocked gate 可修复错误 | `test_one_sentence_video.py` | 已验证 |
| 249-523 | prompt cleanup, duration/shot helpers, style prompt helpers, `_build_style_lock` | 一句话输入清洗、中文/英文静态 prompt、风格锁定基础数据 | `test_one_sentence_video.py`, `test_one_sentence_video_run_types.py` | 已验证 |
| 594-842 | `_storyboard_frame_values`, `_record_one_sentence_text_artifacts`, `_build_one_sentence_episode_outline` | 记录 series/episode 文本产物，未来集生成专属资产 scope | `test_one_sentence_video.py` | 已验证 |
| 919-1055 | trace cleaning, linked asset lookup, reference-generation state, storyboard segment refresh | 参考图恢复后刷新 storyboard/segment reference roles | `test_one_sentence_video.py` | 已验证 |
| 1055-1221 | `_run_one_sentence_expert_reviews`, `_build_storyboard` | style/storyboard 专家审查，首集 materialized storyboard 生成 | `test_one_sentence_video.py` | 已验证 |
| 1221-1309 | response steps, run type validation, duration/budget guards | run_type、real_short 时长和预算校验 | `test_one_sentence_video_run_types.py`, `test_video_production_cost_safety.py` | 已验证 |
| 1326-1389 | reference image generation and error handling | 参考图缺失、超时、provider still running 分支 | `test_one_sentence_video.py` | 已验证 |
| 1389-1545 | `complete_one_sentence_reference_generation` | 服务重启/页面刷新后继续参考图生成并可自动启动图片阶段 | `test_one_sentence_video.py` | 已验证 |
| 1545+ | `create_one_sentence_video` | 一句话总入口：建系列、角色、场景、剧集、分镜、run、文本产物 | `test_one_sentence_video.py`, `test_one_sentence_video_run_types.py` | 已验证 |

## 函数级审查批次 B

文件：`server/app/domains/ai_text_artifacts/ai_text_artifacts_router.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 21-87 | `ArtifactEditRequest`, `ArtifactRegenerateRequest`, `_actor_id`, `_artifact_dict`, `_get_artifact_or_404` | 用户身份、请求 schema、响应字段完整性、404 边界 | `test_ai_text_artifacts_api.py`, `test_ai_text_artifacts_auth_parity.py` | 已验证 |
| 100-153 | `list_artifacts`, `get_artifact`, `get_lineage` | 按 series/episode/run/plan/target/type/status 过滤，血缘版本排序 | `test_ai_text_artifacts_api.py::test_ai_text_artifacts_api_filters_by_run_plan_and_target`, `test_ai_text_artifact_service.py` | 已验证 |
| 174-224 | `edit_artifact`, `approve_artifact`, `regenerate_artifact` | 编辑生成新版本、旧版本审批冲突、AI 再生成进入 reviewable child 版本 | `test_ai_text_artifacts_api.py`, `test_ai_text_artifact_service.py` | 已验证 |

文件：`server/app/domains/ai_text_artifacts/ai_text_artifact_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 34-167 | `AITextArtifactService`, `__init__`, `create_artifact`, `edit_artifact`, `regenerate_artifact` | 版本递增、父子版本、human/AI source_type、run/plan/target 字段保留 | `test_ai_text_artifact_service.py`, `test_ai_text_artifacts_api.py` | 已验证 |
| 167-265 | `regenerate_artifact_with_ai`, `approve_artifact` | LangChain/AI 输出解析、审批只允许最新版本、旧版本 superseded | `test_ai_text_artifacts_api.py::test_ai_text_artifacts_api_regenerate_calls_ai_and_creates_reviewable_child_version`, `test_ai_text_artifacts_api.py::test_ai_text_artifact_api_rejects_approving_stale_version` | 已验证 |
| 266-467 | `latest_approved`, `latest_version`, `list_versions`, `lineage`, `bind_consumer`, `bind_latest_approved_for_episode_run`, `consumed_artifacts_for_run`, `_bind_run_artifact` | run 消费绑定、系列级和剧集级文本产物排序、生产启动引用的是已审批版本 | `test_ai_text_artifact_service.py`, `test_video_production_start_flow_contract.py` | 已验证 |
| 491-646 | `backfill_run_text_artifacts`, `_ensure_approved_legacy_artifact` | 旧 run 补齐剧本/分镜/对白/image/video prompt 文本产物，不覆盖已有版本 | `test_ai_text_artifact_service.py`, `test_series_api.py` | 已验证 |
| 647-799 | `_storyboard_prompt_lines`, `_storyboard_dialogue_lines`, `_legacy_episode_outline`, `_legacy_continuity_ledger`, `_regenerate_*`, `_parse_model_json`, `_next_version`, `_get_artifact` | 旧数据提取、AI 再生成 prompt、JSON fenced/embedded 解析、not found 边界 | `test_ai_text_artifact_service.py`, `test_ai_text_artifacts_api.py` | 已验证 |

文件：`server/app/domains/storyboard_images/storyboard_images_router.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 25-124 | `_auth_user_id`, `create_frame_task`, `create_missing_tasks`, `read_storyboard_images`, `promote_asset` | admin 权限、单帧/批量任务、状态读取、资产提升 API 参数传递 | `test_storyboard_images_api.py`, `test_storyboard_images_auth_parity.py` | 已验证 |

文件：`server/app/domains/storyboard_images/storyboard_image_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 22-111 | `_stable_hash`, `_normalized_frame_id`, `_storyboard_frames`, `_load_storyboard_scope`, `_find_frame` | frame id 归一、episode/run 分镜来源、series/episode/run/frame 不存在错误 | `test_storyboard_image_service.py`, `test_storyboard_images_api.py` | 已验证 |
| 111-259 | `_frame_reference_images`, `_task_idempotency_key`, `_existing_task_for_key`, `_frame_payload`, `_frame_result` | 参考图去重、run-scoped 幂等 key、prompt 缺失阻断、任务 payload 完整 | `test_storyboard_image_service.py::test_force_storyboard_frame_image_payload_uses_fresh_idempotency_key`, `test_storyboard_images_api.py` | 已验证 |
| 259-340 | `create_storyboard_frame_image_task`, `create_missing_storyboard_image_tasks` | force/幂等跳过、批量逐帧失败隔离 | `test_storyboard_image_service.py`, `test_storyboard_images_api.py` | 已验证 |
| 341-497 | `_context_matches_*`, `_latest_tasks_by_frame`, `_latest_assets_by_frame`, `_state_for`, `list_storyboard_image_state` | run 作用域隔离、状态聚合 missing/running/pending/approved/blocked | `test_storyboard_image_service.py::test_storyboard_image_state_is_scoped_by_run_id` | 已验证 |
| 497+ | `promote_storyboard_image_asset` | 只允许 approved 图提升；拒绝显式跨 run/跨 episode；兼容同 episode 无 run_id 旧资产；拒绝 task/asset split context mismatch | `test_storyboard_image_service.py`, `test_storyboard_images_api.py`, `test_storyboard_image_video_bridge.py` | 已验证 |

文件：`server/app/domains/ai_video_series/langchain_runtime/agent_runner.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 18-62 | `extract_json_object`, `_content_from_agent_response` | 纯 JSON、fenced JSON、embedded JSON、非法输出统一映射 | `test_ai_video_langchain_agent_runner.py`, `test_agency_runtime.py` | 已验证 |
| 83-135 | `LangChainAgentRunner.run_json`, `run_structured_ai_video_json` | agent 消息格式、工具注入、默认 validate_json 工具边界 | `test_ai_video_langchain_agent_runner.py`, `test_series_planning_service.py`, `test_script_pipeline.py` | 已验证 |

文件：`server/app/domains/ai_video_series/langchain_runtime/models.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 20-62 | `ensure_langchain_provider_supported`, `build_langchain_openai_kwargs`, `create_chat_model` | 只允许 OpenAI-compatible/chat-completions，base_url/api_key/model 必填，导入无配置副作用 | `test_ai_video_langchain_models.py`, `test_project_langchain_ai_inventory.py` | 已验证 |

文件：`server/app/domains/ai_video_series/langchain_runtime/provider_stage_orchestrator.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 25-69 | `run_provider_stage_agent` | stage 到 submit/query tools 白名单，unsupported stage 拒绝，mock/test agent-runner bypass 走直接工具执行，provider 工具仍经 worker/executor 闸门 | `test_ai_video_langchain_provider_stage_orchestrator.py`, `test_ai_video_langchain_provider_worker.py` | 已验证 |
| 69+ | `_run_provider_tools_directly` | 无 agent_runner 时按 submit/query 顺序执行，成功且无资产时继续 query，有资产或失败立即返回 | `test_ai_video_langchain_provider_stage_orchestrator.py`, `test_ai_video_langchain_provider_tools.py` | 已验证 |

文件：`server/app/domains/ai_video_series/langchain_runtime/provider_tools.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 28-101 | `_load_run_and_job`, `_json_safe`, `_string_value`, `_result_payload` | run/job 绑定校验、结果可 JSON 化、provider task id/status/asset_count 归一 | `test_ai_video_langchain_provider_tools.py`, `test_video_production_real_worker_step.py` | 已验证 |
| 101-133 | `_execute_provider_job`, `_run_provider_job` | provider 工具必须经 worker direct executor，stage mismatch 拒绝 | `test_ai_video_langchain_provider_tools.py`, `test_ai_video_langchain_inventory.py` | 已验证 |
| 133+ | `build_provider_tools` and nested submit/query tools | 图片、视频、合成 submit/query 六个工具，合成兼容 `episode_compose`/`composition` | `test_ai_video_langchain_provider_tools.py`, `test_ai_video_langchain_tools.py` | 已验证 |

文件：`server/app/domains/ai_video_series/langchain_runtime/tools.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 18-59 | `series_context_payload` | series/episode/characters/scenes/story_bible 上下文读取，缺失统一抛 runtime error | `test_ai_video_langchain_tools.py`, `test_series_planning_service.py` | 已验证 |
| 59+ | `build_ai_video_tools` and nested `validate_json`, `read_series_context` | 默认本地工具加 provider tools，allowed_tools 精确限制 provider 编排面 | `test_ai_video_langchain_tools.py`, `test_ai_video_langchain_provider_stage_orchestrator.py` | 已验证 |

文件：`server/app/domains/ai_video_series/status_read_model.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 55-155 | `build_episode_status_matrix`, `_latest_runs_by_episode`, `_active_jobs_by_run` | 每集最新 run、run_id/plan target 双路径 active job 聚合 | `test_ai_video_series_status_read_model.py` | 已验证 |
| 155-311 | `_audit_events_by_run`, `_production_scope_by_run`, `_target_to_run_id`, `_artifact_types_by_episode` | audit event 按 run/production episode/segment 归属，已审批 script/storyboard 标记 | `test_ai_video_series_status_read_model.py` | 已验证 |
| 311+ | `_episode_status_payload` | draft/storyboard_ready 显示 ready_for_image，review/failed/blocked/running-without-job 映射 blocking_code | `test_ai_video_series_status_read_model.py` | 已验证 |

## 函数级审查批次 C

文件：`server/app/domains/ai_video_series/router.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 112-221 | `_domain_http_error`, `auto_generate_series_assets`, `list_series`, `get_style_lock`, `_lifecycle_http_error`, `get_agency_console`, worker-step endpoints, `lock_series_style` | 系列入口、风格锁状态/排队/worker、专家控制台和错误映射 | `test_series_api.py`, `test_series_style_lock_pipeline.py`, `test_agency_console.py` | 已验证 |
| 237-305 | `create_series`, `get_series`, `ensure_series_episodes`, `create_series_story_plan` | 创建剧集占位、详情返回每集 `asset_scope`/`production_status`、故事规划排队 | `test_series_api.py`, `test_series_planning_service.py`, `test_ai_video_series_status_read_model.py` | 已验证 |
| 322-451 | `update_series`, `delete_series`, link/unlink character/scene, `generate_episode_script`, `update_episode` | 剧集脚本/分镜生成入口、人工更新文本产物记录、资产生命周期边界 | `test_series_api.py`, `test_video_production_start_flow_contract.py`, `test_ai_text_artifact_service.py` | 已验证 |

文件：`server/app/domains/ai_video_series/series_planning_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 27-232 | `EpisodePlaceholderResult`, `ContinuityArtifactResult`, `SeriesStoryPlanResult`, `_target_episode_count`, `_style_lock`, `_ids_from_style_lock`, `_episode_outline`, `_continuity_ledger`, `_series_story_plan`, `_season_arc` | 占位剧集数量、风格锁资产池、连续性 ledger、每集 handoff 不完全相同 | `test_series_planning_service.py` | 已验证 |
| 261-418 | `_planning_*`, `_existing_artifact_context`, `_parse_planning_json`, `_episode_outline_sources`, `_merge_series_payload` | 故事专家 prompt/上下文、JSON 解析、从 AI 输出按 episode_number 拆分 outline | `test_series_planning_service.py`, `test_agency_manifest.py` | 已验证 |
| 435-619 | `_normalize_episode_outline`, `_normalize_and_scope_episode_outline`, `_source_has_ids`, `_normalize_existing_episode_outline`, `_should_create_or_replace`, `_content_text`, `_artifact_summary` | 每集 character_ids/scene_ids/generated_assets 归一化；人工版本保留；system backfill 可替换 | `test_series_planning_service.py::test_generate_series_story_plan_creates_episode_specific_assets_from_story_output`, `test_generate_series_story_plan_preserves_human_edit_approved_episode_outline` | 已验证 |
| 651-997 | `ensure_episode_placeholders`, `ensure_series_continuity_artifacts`, `generate_series_story_plan`, `is_series_completed`, `next_episode_number` | 多剧集占位、故事规划产物审批、fallback、完成/下一集判定 | `test_series_planning_service.py`, `test_series_api.py` | 已验证 |

文件：`server/app/domains/ai_video_series/story_planning.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 36-174 | `StoryPlanningDomainError`, `_utc_now_iso`, `story_planning_in_progress_error`, `active_story_plan_job`, `set_story_planning_state`, `enqueue_story_plan_job` | 故事规划状态持久化、重复 active job 阻断、queue idempotency | `test_series_api.py`, `test_series_style_lock_pipeline.py` | 已验证 |
| 174-302 | `start_story_plan`, `run_story_plan_job`, `run_story_plan_worker_step` | 已完成规划复用、queued/running/completed/fallback/failed 生命周期、worker lease | `test_series_api.py`, `test_style_lock_background_worker.py`, `test_series_style_lock_pipeline.py` | 已验证 |

文件：`server/app/domains/ai_video_series/story_generator_expert.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 35-207 | `StoryGeneratorResult`, `_source`, `_context_hash`, `_supports_json_schema_response`, `_response_format`, `_split_model_response`, `_parse_json_object`, `_validate_story_payload`, `_build_prompts` | 专家来源追溯、JSON schema 能力、非法输出映射、prompt 明确禁止全系列资产机械复制到每集 | `test_series_planning_service.py`, `test_agency_manifest.py` | 已验证 |
| 234-406 | `generate_story_plan_with_expert`, `_finalize_failed` | LangChain tools 路径、专家 invocation/audit、超时/限流/HTTP/OpenAI 异常归一 | `test_series_planning_service.py`, `test_agency_runtime.py`, `test_project_langchain_ai_inventory.py` | 已验证 |

文件：`server/app/domains/ai_video_series/episode_asset_scope_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 21-130 | `EpisodeAssetScopeError`, `normalize_episode_asset_scope`, `_dedupe_strings` | 每集资产作用域主入口：优先显式 IDs，再用 generated_assets，再最小 fallback | `test_series_planning_service.py::test_generate_series_story_plan_creates_episode_specific_assets_from_story_output`, `test_generate_series_story_plan_missing_episode_ids_falls_back_to_primary_asset_only` | 已验证 |
| 145-299 | `_usage_by_id`, `_series_*`, `_find_series_*_by_name`, `_create_generated_characters`, `_create_generated_scenes`, `_generated_meta` | 按 episode 生成新角色/场景并标记来源，避免名字重复创建 | `test_series_planning_service.py` | 已验证 |
| 311-446 | `_fallback_character`, `_fallback_scene`, `_validate_characters`, `_validate_scenes`, `_character_usage`, `_scene_usage`, `_default_usage` | fallback 选择、跨系列非法 ID 拒绝、资产用途标注 | `test_series_planning_service.py`, `test_video_production_start_flow_contract.py` | 已验证 |

文件：`server/app/domains/ai_video_series/style_lock.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 92-212 | `StyleLockDomainError`, `auto_generate_series_assets`, `missing_agency_trace`, `timeout_agency_trace`, `agency_trace_blocks` | 自动生成角色/场景、专家配置缺失/超时 trace、blocked 不应锁定 | `test_series_style_lock_pipeline.py`, `test_agency_orchestrator.py` | 已验证 |
| 253-474 | `style_lock_status`, `style_lock_payload`, reference progress helpers, `set_style_lock_state`, `record_style_lock_series_bible_artifact` | 风格锁状态读取、reference_progress 实时回传、series_bible 文本产物落库/审批 | `test_series_style_lock_pipeline.py`, `test_ai_text_artifact_service.py` | 已验证 |
| 474-635 | active/enqueue/start style lock, `parse_json_with_key`, `generate_reference_image`, `generate_reference_image_isolated` | 重复任务阻断、异步排队、参考图生成失败不抛穿主流程 | `test_series_style_lock_pipeline.py`, `test_style_lock_background_worker.py` | 已验证 |
| 660-888 | `ensure_series_assets`, `fill_reference_assets` and nested `run_job` | 缺角色/场景补齐、多角度角色/场景参考图、slot-scoped idempotency、并发生成 | `test_series_style_lock_pipeline.py` | 已验证 |
| 888-1068 | `build_story_bible`, `run_style_lock_job`, `run_style_lock_worker_step` | 最终 story_bible、agency review blocked/timeout、worker lease/失败重试 | `test_series_style_lock_pipeline.py`, `test_style_lock_background_worker.py` | 已验证 |

文件：`web/src/router/index.js`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 141-153 | `series/:id`, `series/:seriesId/agency-console`, `series/:seriesId/ai-text-artifacts` | 文本追溯台前端路由存在，SeriesDetail/Monitor 跳转目标一致 | `web/src/__tests__/api-clients.test.js`, `web/src/__tests__/ai-text-artifact-workbench.test.js` | 已验证 |

文件：`web/src/views/AITextArtifactWorkbenchPage.vue`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 116-184 | `formatJson`, `shortId`, artifact target/list/select helpers | 每集文本产物显示 Exx/标题，避免“只看到 ID 看不到剧集” | `web/src/__tests__/ai-text-artifact-workbench.test.js` | 已验证 |
| 184-248 | `load`, `saveEdit`, `approve`, `regenerate`, `onMounted` | 按 `series_id`/`episode_id` 加载、编辑、审批、AI 再生成后保持选中新版本 | `web/src/__tests__/ai-text-artifact-workbench.test.js`, `web/src/__tests__/api-clients.test.js` | 已验证 |

文件：`web/src/views/SeriesDetailPage.vue`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 490-589 | active run/episode/story-plan computed helpers | 可生产剧集、缺占位、故事规划状态、按钮禁用和文案 | `web/src/__tests__/series-detail-agency.test.js`, `web/src/__tests__/series-detail-video-production.test.js` | 已验证 |
| 612-718 | `nextEpisode`, `beginEditSeries`, `errorMessage`, reference URL/progress helpers | 下一集、编辑入口、错误归一化、托管/过期 URL 过滤、角色/场景参考图进度 patch | `web/src/__tests__/series-detail-agency.test.js`, `web/src/__tests__/series-detail-video-production.test.js` | 已验证 |
| 731-873 | `toggleEpisodeText`, `refreshEpisodeTextArtifacts`, latest artifact/source/text/scope helpers | 每集剧本/分镜/outline 优先显示已审批 AI 文本产物，asset_scope 显示角色/场景差异 | `web/src/__tests__/series-detail-agency.test.js` | 已验证 |
| 873-1008 | storyboard frame/image helpers and script generation action | 每集分镜帧、分镜图状态、单帧/批量生成、单集剧本生成 | `web/src/__tests__/series-detail-agency.test.js`, `web/src/__tests__/series-detail-video-production.test.js` | 已验证 |
| 1054-1088 | `saveSeries`, `removeCharacter`, `removeScene`, `removeSeries` | 系列详情页保存和删除操作，角色/场景解绑后刷新详情 | `web/src/__tests__/series-detail-agency.test.js`, `web/src/__tests__/series-detail-video-production.test.js` | 已验证 |
| 1104-1219 | `generateStoryPlan`, `lockStyle`, style/story-plan polling | 故事规划/风格锁定异步状态刷新，终态后刷新文本产物 | `web/src/__tests__/series-detail-agency.test.js`, `web/src/__tests__/series-detail-video-production.test.js` | 已验证 |
| 1207-1299 | `startPipelineRun`, `maybeAutostartProduction`, `autoGenerate`, status classes | 自动补剧集、缺文本先生成脚本、风格锁完成后启动单集生产 | `web/src/__tests__/series-detail-video-production.test.js` | 已验证 |

文件：`web/src/views/VideoProductionMonitorPage.vue`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 419-489 | production/readiness/cost/storyboard image computed helpers | 生产主动作、文本产物入口、readiness repair route、分镜图摘要 | `web/src/__tests__/video-production-monitor-page.test.js`, `web/src/__tests__/video-production-monitor-boundary-states.test.js` | 已验证 |
| 491-727 | load helpers, storyboard image promotion helpers | run/tree/readiness/provider tasks/repair/storyboard images 并发加载，已审批分镜图提升到视频资产 | `web/src/__tests__/video-production-monitor-page.test.js`, `web/src/__tests__/api-clients.test.js` | 已验证 |
| 727-974 | tree/segment detail, polling, autopilot, stage actions, repair/retry | 图片/视频/合成/worker 手动动作、状态轮询、返修和 retry impact | `web/src/__tests__/video-production-monitor-page.test.js`, `web/src/__tests__/video-production-repair-node.test.js` | 已验证 |

## 函数级审查批次 D

文件：`server/app/domains/video_production/provider_stage_executor.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 72-126 | `_provider_stage_lock`, `assert_paid_submit_deployment_safe` | 付费 provider 单进程提交契约、worker count 必须显式为 1 | `test_provider_throttle_and_backoff.py`, `test_provider_stage_executor.py` | 已验证 |
| 126-292 | `ProviderStageExecutor.execute` | 能力/预算/幂等/task/reservation/submit/sync 主编排；provider I/O 不在数据库事务里 await | `test_provider_stage_executor.py::test_executor_submits_syncs_settles_and_audits_provider_stage`, `test_provider_stage_executor.py::test_provider_io_is_not_awaited_inside_sqlalchemy_transaction` | 已验证 |
| 292-512 | estimated cost、payload、existing task、submit claim、capacity、reservation/reload/transaction helpers、`_close_transaction` | 预算必须为正、payload drift 拒绝、丢失 submit claim 或 reservation 进入可修复状态、并发限流写入 retry_wait，事务后关闭幂等 | `test_provider_stage_executor.py`, `test_provider_throttle_and_backoff.py` | 已验证 |
| 513-716 | provider task id、submit failure、`_handle_sync_result` completed/failed/cancelled/pending 分支 | 缺 provider_task_id 标记 repairable；成功结算；失败资产、quota/rate limit、terminal failure 不误记成功 | `test_provider_stage_executor.py`, `test_provider_throttle_and_backoff.py` | 已验证 |
| 716-946 | failed assets、quota 判断、usage cost、sync_required/succeeded/failed 状态回写、`_archived_idempotency_key` | 缺 usage cost 进入 stale repair；sync_required 不消耗成功；可重试 quota 归档旧 key 以允许新提交 | `test_provider_stage_executor.py`, `test_provider_cost_reservation_service.py` | 已验证 |

文件：`server/app/domains/video_production/provider_stage_task_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 21-53 | `request_hash`, `provider_stage_idempotency_key` | provider payload hash 稳定，幂等 key 覆盖 run/stage/target/provider/model | `test_provider_stage_executor.py::test_request_hash_is_stable_independent_of_key_order` | 已验证 |
| 53-131 | `get_or_create_stage_task`, `set_task_status`, `claim_stage_task_for_submit` | 幂等创建、payload drift 拒绝、状态机校验、reserved 到 submitted 原子认领 | `test_provider_stage_executor.py`, `test_provider_throttle_and_backoff.py` | 已验证 |

文件：`server/app/domains/video_production/provider_cost_reservation_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 31-123 | plan locks/loaders、reservation loader、state error、`active_reserved_cost` | plan 级锁、sqlite/non-sqlite lock 路径、只统计活跃预留 | `test_provider_cost_reservation_service.py` | 已验证 |
| 123-212 | `create_cost_reservation`, `mark_reservation_submitted`, `mark_reservation_stale_needs_repair` | 预算上限包含 current+active+new；非法状态转 repairable | `test_provider_cost_reservation_service.py`, `test_provider_stage_executor.py` | 已验证 |
| 212-304 | `settle_reservation`, `release_unsubmitted_reservation`, `expire_unsubmitted_reservations` | 结算幂等、stale 也可结算、释放/过期状态正确 | `test_provider_cost_reservation_service.py` | 已验证 |

文件：`server/app/domains/video_production/video_production_readiness.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 24-163 | counts/assets/block helpers and gate relevance | 只统计 latest、按状态判断 image/video/final gate 是否相关 | `test_video_production_readiness.py` | 已验证 |
| 163-181 | `_blocked_compose_jobs` | final_review_pending 无最终资产时暴露被阻断合成 job 的修复入口 | `test_video_production_readiness.py::test_readiness_blocks_final_review_when_compose_job_blocked_without_final_asset` | 已验证 |
| 181+ | `build_run_readiness` | start image/video/compose/final 的 can_*、next_action、review/production repair blocks | `test_video_production_readiness.py` | 已验证 |

文件：`server/app/domains/video_production/video_production_router.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 64-181 | request schema classes | create/start/one-sentence/review/void/edit/regenerate/bulk/worker/collection 请求字段边界 | `test_video_production_api.py`, `test_one_sentence_video.py`, `video-production-run-type-api.test.js` | 已验证 |
| 185-463 | payload helpers、status/page filters、asset summary、mock error、review gate counts、provider task payload | run/asset/provider task 响应、权限字段、review gate counts、pagination 上限 | `test_video_production_api.py`, `test_video_production_provider_stage_tasks_api.py` | 已验证 |
| 510-766 | `create_run`, `start_run`, `one_sentence_video`, background reference completion, get/backfill, mock/real worker endpoints | 单集/一句话入口、后台参考图恢复、真实 worker async mode、错误映射 | `test_video_production_api.py`, `test_one_sentence_video.py`, `test_video_production_real_worker_step.py` | 已验证 |
| 766-1067 | readiness、provider-stage-tasks、tree、costs、segment detail/retry impact、pause/resume | 生产监控可见性、成本、任务、树、暂停恢复 | `test_video_production_readiness.py`, `test_video_production_provider_stage_tasks_api.py`, `test_video_production_tree_api.py`, `test_video_production_pause_resume.py`, `test_video_production_retry_impact.py` | 已验证 |
| 1067-1341 | review-items、edit/void/persist-retry/retry segment/bulk review/collection | 审查列表、持久化重试先 AI 审核、版本 void、批量审批、片段 retry | `test_video_production_api.py`, `test_video_production_tree_api.py`, `test_video_production_retry_impact.py` | 已验证 |
| 1373-1530 | start/sync images/videos/compose, regenerate/start/sync regeneration | 图片/视频/合成阶段路由和资产重生成路由 | `test_video_production_api.py`, `test_video_production_full_mocked_e2e.py`, `test_video_production_state_machine.py` | 已验证 |

## 函数级审查批次 E

文件：`server/app/domains/video_production/production_queue_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 30-99 | `_active_plan_ids_query`, `_ensure_plan_accepts_jobs`, `enqueue_job` | 只向 active plan 入队，幂等 key 复用，integrity race 可恢复 | `test_production_queue_service.py` | 已验证 |
| 100-180 | `claim_next_job`, `release_expired_leases` | worker lease、plan 过滤、抢占 race 跳过、过期 lease 回队 | `test_production_queue_service.py`, `test_agency_backtrack_policy.py` | 已验证 |
| 181-316 | `mark_job_completed`, `fail_job`, `retry_job_without_attempt` | job 完成/失败/重试等待状态机，attempt/max_attempts 边界 | `test_production_queue_service.py` | 已验证 |
| 317-360 | `pause_plan_jobs`, `resume_plan_jobs` | 暂停只影响 queued/retry_wait，恢复后仍可 claim | `test_production_queue_service.py`, `test_production_cost_service.py` | 已验证 |

文件：`server/app/domains/video_production/asset_storage_guard.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 26-152 | storage failure、private host、local path、checksum、download helpers | 阻断本地/私网 provider URL，限制本地文件根目录，校验资产类型并记录 repairable failure | `test_asset_storage_guard.py` | 已验证 |
| 153+ | `persist_provider_asset` | provider 产物持久化、URL/本地文件双路径、checksum/size 落库 | `test_asset_storage_guard.py`, `test_video_production_api.py`, `test_video_production_real_worker_step.py` | 已验证 |

文件：`server/app/domains/video_production/production_plan_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 36-177 | style lock/frame/duration/reference helpers | 分镜 frame、时长切段、角色/场景/style reference roles 进入生产计划 | `test_video_production_start_flow_contract.py`, `test_video_production_tree_api.py` | 已验证 |
| 178-390 | `create_episode_production_plan`, `ensure_episode_production_plan`, `ensure_shot_segments` | plan/episode/scene/shot/segment materialize，重复调用幂等 | `test_video_production_start_flow_contract.py`, `test_video_production_mocked_e2e.py`, `test_video_production_tree_api.py` | 已验证 |

文件：`server/app/domains/video_production/production_gate_evaluator.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| 22-92 | stage asset type、required ids、latest assets、blocked reason、`evaluate_stage_gate` | image/video/compose gate 只看 latest 资产，缺失/失败/待审/拒绝原因可追踪 | `test_production_gate_evaluator.py`, `test_video_production_readiness.py` | 已验证 |

文件：`server/app/domains/video_production/production_cost_service.py` 与 `production_cost_summary_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| cost_service:16-111 | plan lookup、budget assert、cost event、budget pause | 预算超限阻断并暂停 plan job，实际成本事件累加 | `test_production_cost_service.py`, `test_video_production_costs_api.py` | 已验证 |
| summary:31-122 | reservation aggregation、`get_run_costs` | 已结算/活跃/过期 reservation 与 actual cost 汇总，linked/unlinked run 边界 | `test_provider_cost_reservation_service.py`, `test_video_production_costs_api.py` | 已验证 |

文件：`server/app/domains/video_production/production_tree_service.py` 与 `production_segment_detail_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| `mock_scale_scheduler_service.py`:53+ | `_clean_prompt`, `_title_from_prompt`, `_segment_durations`, `_create_series_episode`, `_create_plan_tree`, `_next_mock_asset_version`, `_register_mock_segment_asset`, `advance_mock_scheduler`, `mock_series_scale` | 一句话 provider-free 长时长 mock scale，prompt/title 清洗、批量 segment 调度和 production tree 路径 | `test_mock_scale_scheduler_service.py` | 已验证 |
| tree:35-205 | pagination、plan/episode/scene/shot/asset/job/segment payload helpers | 生产树响应字段、最新资产、job、repair node 结构 | `test_video_production_tree_api.py`, `test_mock_scale_scheduler_service.py` | 已验证 |
| tree:207-382 | `get_run_tree`, jobs/assets/repair node loaders | run/plan 双入口、分页、状态过滤、repair node 聚合 | `test_video_production_tree_api.py`, `test_video_production_retry_impact.py` | 已验证 |
| detail:18-50 | `_asset_payload`, `get_segment_detail` | segment 详情含最新 asset、job history、history limit | `test_video_production_segment_detail_api.py` | 已验证 |

文件：`server/app/domains/video_production/production_retry_service.py`, `production_review_service.py`, `review_asset_edit_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| retry:19-159 | retry impact、retry segment、stage job enqueue | 返修影响范围、segment 状态回退、下游 job 重建 | `test_video_production_retry_impact.py`, `test_video_production_tree_api.py` | 已验证 |
| review:20-85 | bulk review snapshot、approvable guard、`apply_bulk_review_action` | 批量审批去重、stale/latest/final gate 边界 | `test_production_bulk_review.py`, `web/src/__tests__/review-bulk-actions.test.js` | 已验证 |
| edit:22-223 | void、image edit reserve、stale/version/provider failure helpers | 审核页 void 旧版本、图片编辑幂等/预算/provider 失败映射 | `test_video_production_api.py`, `web/src/__tests__/ai-video-review-page.test.js` | 已验证 |

文件：`server/app/domains/video_production/video_production_state.py`, `production_state_contract.py`, `production_status_aggregation.py`, `video_production_run_types.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| state:17-175 | frame ids、latest assets、start gate、stage task、run gate recompute | 图片/视频/合成启动条件和 run gate 状态回写 | `test_video_production_state_machine.py`, `test_production_gate_evaluator.py` | 已验证 |
| contract:84-108 | active provider task、reviewable asset、transition validation | 状态枚举边界、非法 transition 拒绝 | `test_video_production_boundary_models.py`, `test_video_production_named_errors.py` | 已验证 |
| aggregation:11-42 | parent status aggregation、`recompute_from_segment` | segment 变更后 shot/scene/episode/plan 父状态同步 | `test_video_production_pause_resume.py` | 已验证 |
| run_types:18-81 | validate/get/set/assert/is real/mock run type | legacy/real/mock run type 校验和前后端 API 映射 | `test_video_production_run_type.py`, `web/src/__tests__/video-production-run-type-api.test.js` | 已验证 |

文件：`server/app/domains/video_production/provider_capability_service.py`, `production_action_result.py`, `production_errors.py`, `production_collection_service.py`

| 行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| capability:27-60 | capability merge、paid submit allowlist | provider 模型能力配置合并，real paid 必须显式允许 | `test_video_production_provider_config.py`, `test_video_production_cost_safety.py` | 已验证 |
| action/errors | `ProductionActionResult`, `ProductionRepairableError`, `to_http_detail` | worker/router repairable 错误统一返回 code/detail | `test_video_production_named_errors.py`, `test_video_production_real_worker_step.py` | 已验证 |
| collection:13-80 | `create_collection_from_approved_episodes` | 只从已审批成片剧集生成合集，缺失/未完成时报错 | `test_collection_builder.py`, `test_long_video_mocked_e2e.py` | 已验证 |

文件：`server/app/domains/agency_operations`

| 文件/行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| `agency_orchestrator.py`:89-787 | 专家调用准备、幂等、runtime config/manifest blocker、debate trace 合并 | AI 视频专家团队是否启用、缺配置阻断、通过/阻断 trace | `test_agency_orchestrator.py`, `test_agency_runtime.py`, `test_agency_manifest.py` | 已验证 |
| `agency_debate_*`, `agency_scorecard_contracts.py` | 多专家辩论、scorecard、repair intent | blocking verdict 触发修复意图，不通过时阻断 provider 阶段 | `test_agency_debate_policy.py`, `test_agency_debate_audit.py`, `test_agency_scorecard_contracts.py` | 已验证 |
| `agency_repair_*`, `agency_backtrack_policy.py` | 自动修复分类、入队、执行、回退策略 | repair job 入队、预算、重试授权、下游 image job 重建 | `test_agency_repair_*.py`, `test_agency_backtrack_policy.py` | 已验证 |
| `agency_creative_patch_service.py`:33-793 | creative patch 创建/审批/应用、文本产物回写、unresolved gate | 未处理 patch 阻断 provider；应用后同步 script/storyboard/prompt artifact | `test_agency_creative_patch_service.py`, `test_video_production_creative_patch_gate.py` | 已验证 |
| `agency_router.py`, `agency_console.py`, `video_agency_team.py` | 专家控制台、repair/patch API、团队画像 | 控制台可解释阻断、repair task/action、专家团队角色展示 | `test_agency_api.py`, `test_agency_console.py`, `web/src/__tests__/agency-console-page.test.js` | 已验证 |

文件：`web/src/views/AIVideoReviewPage.vue`, `web/src/views/OneSentenceVideoPage.vue`, `web/src/api/videoProduction.js`, `web/src/api/storyboardImages.js`, `web/src/api/agency.js`

| 文件/行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| `AIVideoReviewPage.vue`:321-808 | review list、gate tabs、bulk approve、void、image edit、retry persist、sync/regenerate | 审核页覆盖人工审批、边界 gate、批量动作、stale 刷新、图片编辑和返修入口 | `web/src/__tests__/ai-video-review-page.test.js`, `web/src/__tests__/ai-video-review-boundary-gates.test.js`, `web/src/__tests__/review-bulk-actions.test.js` | 已验证 |
| `OneSentenceVideoPage.vue`:251-667 | run type/duration、agency trace、autopilot、submit、error normalization | 一句话 real/mock 入口、时长上限、自动推进、pending provider/repair 错误展示 | `web/src/__tests__/one-sentence-video-page.test.js`, `web/src/__tests__/one-sentence-auto-repair-policy.test.js` | 已验证 |
| `videoProduction.js`:11-298 | 生产 API client 全入口 | run/tree/readiness/cost/review/provider/collection/one-sentence 参数正确 | `web/src/__tests__/api-clients.test.js`, `web/src/__tests__/video-production-run-type-api.test.js` | 已验证 |
| `storyboardImages.js`, `agency.js` | 分镜图和专家团队 API client | 分镜图任务/提升、专家/patch/repair/multimodal review API 路径正确 | `web/src/__tests__/api-clients.test.js`, `web/src/__tests__/agency-api.test.js` | 已验证 |

文件：覆盖审计补充 - AI 视频支撑模块

| 文件/行号 | 函数组 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| `server/app/domains/video_production/*.py`:1+, `server/app/domains/ai_video_series/*.py`:1+, `server/app/domains/ai_text_artifacts/*.py`:1+, `server/app/domains/storyboard_images/*.py`:1+, `server/app/domains/agency_operations/*.py`:1+, `server/app/domains/system_configuration/*.py`:1+, `server/app/domains/system_operations/*.py`:1+, `server/app/domains/model_configuration/*.py`:1+, `server/app/domains/pixelle_integration/*.py`:1+, `server/app/domains/script_pipeline/*.py`:1+, `server/app/db/models/*.py`:1+, `server/app/main.py`:1+, `server/scripts/smoke_bailian_one_sentence_e2e.py`:1+, `server/scripts/check_chinese_comments.py`:1+, `server/scripts/check_ai_video_report_coverage.py`:1+, `web/src/router/index.js`:1+, `web/src/views/*.vue`:1+, `web/src/api/*.js`:1+ | owner 边界归属补充 | 机械检查只证明这些源码行归入本报告范围，防止文件/声明漏点；行为、风险和语义审查以上方具体函数组/模块行号表和专项测试为准 | `check_ai_video_report_coverage.py`, `test_ai_video_report_coverage_checker.py` | 已验证 |
| `agency_contracts.py`:15-169, `agency_runtime_contracts.py`:10-38 | 专家执行状态、console payload、runtime error/setting contract | 专家调用状态枚举、console 响应结构、runtime 错误码和默认配置读取 | `test_agency_invocation_models.py`, `test_agency_runtime.py`, `test_ai_video_langchain_models.py` | 已验证 |
| `agency_manifest.py`:42-210, `agency_runtime.py`:68-275 | expert manifest、legacy expert 读取、runtime secret redaction、专家输出解析 | manifest hash/路径安全、专家 markdown 读取、模型调用脱敏、JSON/fenced JSON/错误码映射 | `test_agency_manifest.py`, `test_agency_runtime.py`, `test_agency_orchestrator.py` | 已验证 |
| `agency_debate_policy.py`:12-112, `agency_debate_audit.py`:33-434 | debate policy、角色调用、scorecard/repair intent 生成 | 不同 stage 辩论策略、blocking verdict、repair intent、幂等审计 trace | `test_agency_debate_policy.py`, `test_agency_debate_audit.py`, `test_agency_scorecard_contracts.py` | 已验证 |
| `agency_creative_patch_contracts.py`:14-160 | creative patch 枚举、payload normalize | patch 类型/目标/字段白名单，非法 after payload 拒绝 | `test_agency_creative_patch_contracts.py`, `test_agency_creative_patch_service.py` | 已验证 |
| `agency_multimodal_review.py`:17-122 | multimodal asset context 和图片/视频审查分发 | 真实资产 URL/prompt 输入，图片与视频审查路由，缺缩略图视频 URL 透传 | `test_agency_multimodal_review.py` | 已验证 |
| `agency_persistence.py`:22-216 | invocation 幂等创建、完成落库和 audit | 唯一键 race 恢复、非同类 IntegrityError 透出、失败/成功 finalization 幂等 | `test_agency_persistence.py`, `test_video_production_observability_events.py` | 已验证 |
| `agency_prompting.py`:14-106 | expert prompt 与 media input 组装 | stage/role/context/markdown 进入 expert payload，多媒体输入保留 | `test_agency_runtime.py` | 已验证 |
| `agency_repair_classifier.py`:21-148, `agency_repair_contracts.py`:12-145 | repair task 分类、可读性 fallback、action 映射 | unreadable/generic finding 进入人工确认，自动修复类型白名单和目标 action | `test_agency_repair_classifier.py`, `test_agency_repair_loop.py` | 已验证 |
| `agency_repair_executor.py`:31-369, `agency_repair_orchestrator.py`:17-269 | repair job 入队、预算、执行、下游 image job 重建 | 自动修复轮次、预算可用性、manual paid block、prompt 微调、缺参考图阻断 | `test_agency_repair_executor.py`, `test_agency_repair_orchestrator.py`, `test_agency_auto_repair_e2e.py` | 已验证 |
| `server/app/db/models/video_production.py` | 生产计划、剧集、场景、镜头、segment、job、provider task、资产、审核和成本 ORM 边界 | SQLAlchemy metadata 归属、表名注册、clean-process import | `test_video_production_orm_boundary.py` | 已验证 |
| `server/app/db/models/ai_video_series.py` | series/episode 与视频生产 run ORM 关联边界 | metadata 归属、核心表注册 | `test_ai_video_series_orm_boundary.py` | 已验证 |
| `server/app/db/models/ai_text_artifacts.py` | 剧本/分镜文本产物和 consumer ORM 边界 | metadata 归属、表注册、clean-process import | `test_ai_text_artifact_orm_boundary.py` | 已验证 |
| `server/app/db/models/agency_operations.py` | 专家调用、scorecard、creative patch、repair task ORM 支撑 | invocation 表 shape、public status/trace serialization、控制台读取 | `test_agency_invocation_models.py`, `test_agency_console.py` | 已验证 |
| `server/app/db/models/image_production.py` | 分镜图任务/资产/审核/策略 ORM 支撑 | image creation asset/task/review/strategy 表注册、FK/index 形状 | `test_image_production_orm_boundary.py`, `test_image_creation_models.py` | 已验证 |
| `server/app/db/models/model_configuration.py`, `server/app/db/models/system_configuration.py` | AI 模型配置与系统设置 ORM 边界 | `ai_models`/`system_settings` 表注册、clean-process import | `test_model_configuration_orm_boundary.py`, `test_system_configuration_orm_boundary.py` | 已验证 |
| `server/app/db/models/production_observability.py` | 生产审计事件 ORM 边界 | `production_audit_events` 表注册、clean-process import | `test_production_audit_event_orm_boundary.py` | 已验证 |
| `server/app/db/models/script_pipeline.py` | 剧本输出 ORM re-export 边界 | episode script、dramatic beat、scene outline、visual shot 模型 re-export 和表注册 | `test_script_output_orm_boundary.py` | 已验证 |
| `ai_video_series/artifacts.py`:1-224 | 剧集更新文本产物、story plan artifact、完成态回填 | episode 更新写 script/storyboard 文本，story plan payload 从 artifact 恢复并标记完成 | `test_ai_text_artifact_service.py`, `test_series_api.py`, `test_series_planning_service.py` | 已验证 |
| `ai_video_series/read_models.py`:1-241, `schemas.py`:11-84 | 系列/剧集响应、资产引用、agency console 聚合、请求 schema | series/episode public shape、active video run 合并、reference status、请求字段边界 | `test_ai_video_series_read_models.py`, `test_ai_video_series_status_read_model.py`, `test_series_api.py` | 已验证 |
| `production_segment_service.py`:12-18, `production_status.py`:6-55 | segment retry 和生产状态常量 | retry 生成 superseded/retry_queued 新 segment，状态常量被 queue/review/tree/readiness 复用 | `test_production_bulk_review.py`, `test_video_production_tree_api.py`, `test_production_queue_service.py` | 已验证 |
| `system_health_router.py`, `crypto.py` | 真实 provider 健康预检、敏感配置加密 | provider capability readiness、settings key 加密/保留 | `test_system_health_page_contract.py`, `test_settings_endpoints.py`, `test_ai_config*.py` | 已验证 |
| `ai_models_router.py`, `ai_generator.py`:21-309, `runtime_model_config.py`:12-125, `model_schema.py`:9-49, `model_registry.py`:15-45, `migration.py`:23-54 | AI 模型配置 API、LangChain/OpenAI-compatible client、scene/capability resolution、legacy settings migration | `/ai-models*` 路由、专家/图片/视频/合成模型解析、连接配置脱敏、旧 settings 幂等迁移 | `test_ai_config*.py`, `test_ai_generator.py`, `test_model_schema.py`, `test_model_registry.py`, `test_ai_model_migration.py`, `api-clients.test.js`, `ai-config-page.test.js` | 已验证 |
| `pixelle_client.py`:25-173, `pixelle_stage_client.py`:1+, `pixelle_execution_service.py`:19-114, `pixelle_router.py`:28-458 | Pixelle/DashScope/local compose provider client、stage submit/query、合成配置/代理、视频阶段 frame payload | base URL/API key fallback、请求重试/错误、stage metadata、config 脱敏、AI model 序列化；DashScope async image/video 直连覆盖 `_submit_dashscope_async_image_batch`、`_submit_dashscope_video_batch`，`local_ffmpeg_compose` 覆盖 `_compose_segments_with_ffmpeg`、`_submit_local_ffmpeg_compose` | `test_pixelle_client.py`, `test_pixelle_stage_client.py::test_submit_image_batch_uses_dashscope_async_image_generation_when_configured`, `test_pixelle_stage_client.py::test_submit_video_batch_uses_dashscope_async_and_get_stage_task_queries`, `test_pixelle_stage_client.py::test_submit_compose_uses_local_ffmpeg_protocol`, `test_pixelle_config_serialization.py`, `test_pixelle_config_security.py`, `test_image_creation_pixelle_client.py` | 已验证 |
| `pipeline_router.py`:25-584, `script_pipeline_service.py`:60-977, `storyboard_timing.py`:14-228 | 剧本 pipeline API、stage runner、gate runner、AI 文本产物写入、秒级 timing/prompt | pipeline start/list/get、专家 gate 阻断、provider rendering job gate、阶段恢复、分镜 timing 和详细 prompt | `test_script_pipeline.py`, `test_script_pipeline_provider_tools.py`, `test_pipeline_saved_storyboard_compat.py`, `test_script_pipeline_auth_parity.py` | 已验证 |
| `oss_service.py` | 上传 helper 本地 fallback | 本地 provider 返回 file URL，缺文件抛错；远端 OSS 分支不作为本轮主链路证据 | `test_system_operations_oss_service.py` | 已验证 |
| `server/scripts/smoke_bailian_one_sentence_e2e.py` | 真实付费 smoke 的 opt-in、resume、provider blocker 和单任务批处理保护 | 未授权安全退出；已完成阶段跳过；`PROVIDER_THROTTLED`/`BUDGET_BLOCKED` 停止；显式 `--retry-provider-blockers` 仅清当前 run episode scope | `test_bailian_smoke_script_contract.py` | 已验证 |
| `server/scripts/check_chinese_comments.py` | 审查报告辅助检查器 | AI 视频域源码中文模块说明、声明契约和高风险 provider/browser 调用边界注释检查；不属于生产链路 | `test_chinese_comment_checker.py` | 已验证 |
| `server/scripts/check_ai_video_report_coverage.py`:38+ | 审查报告覆盖复核器 | AST 扫描本报告范围内 Python 函数/类声明，用轻量正则扫描前端 AI 视频主链路 JS/Vue 声明，并校验报告中 `.py/.js/.vue/.md` 文件引用与 Python pytest node 引用可解析；不属于生产链路 | `server\.venv\Scripts\python.exe server\scripts\check_ai_video_report_coverage.py --report docs\superpowers\reports\2026-06-22-ai-video-generation-code-review-audit.md`, `test_ai_video_report_coverage_checker.py` | 已验证 |
| `AIConfigPage.vue` | AI 模型配置页 | 创建专家团队审阅模型时写入 `scene_key` 和 `protocol` | `ai-config-page.test.js` | 已验证 |
| `web/src/api/aiConfig.js`, `web/src/api/settings.js` | 前端模型配置和系统设置 API client | `/ai-models*`、`/settings` 请求路径和 payload 形状 | `api-clients.test.js`, `ai-config-page.test.js` | 已验证 |
| `AgencyConsolePage.vue`:232-559, `web/src/api/series.js`:11-77 | 专家控制台加载、poll、patch/repair 动作、series API client | console/repair/patch UI 状态和 API 路径，3D 团队图懒加载 | `agency-console-page.test.js`, `agency-3d-lazy-load.test.js`, `api-clients.test.js` | 已验证 |
| `SeriesListPage.vue`:102-157 | 系列列表创建入口 | 类型加载、创建表单、状态展示、错误展示 | `series-list-page.test.js` | 已验证 |

范围边界：`imageProduction.js`, `videos.js`, `ImageProductionStrategiesPage.vue`, `VideosPage.vue`, `VideoStudio.vue` 属于旧图片策略/素材库/单视频工作台导航面，不是本轮多剧集 AI 视频生产主链路；`characters.js`, `scenes.js`, `pipeline.js`, `director.js` 也会被 `api-clients.test.js` 的外围 client 用例覆盖，但本轮路由/API client owner 口径只点名多剧集 AI 视频生产主链路和模型/系统配置支撑面；上述外围入口不作为“多剧集 AI 视频生成全链路已跑通”的证据。
文件：真实浏览器登录态 smoke

| 页面 | 审查重点 | 证据 | 状态 |
| --- | --- | --- | --- |
| `/series/f49718b7-e0ec-4012-b7fa-5c5229105d47/ai-text-artifacts` | 已登录后不再 404/不跳登录页；AI 文本追溯台显示文本产物、剧集标签、编辑/审批/再生成文案 | Playwright + 系统 Chrome：login `200`，page `200`，URL 保持目标页，36 个文本产物匹配项，badResponses/requestfailed 均为空 | 已验证 |

## 独立 code review 处置

七轮审查子代理结论：前三轮发现的问题已处理；第四轮发现后台 review 状态 repair job 漏扫、direct provider helper 缺少无 runner 测试、报告措辞不精确，已处理；第五轮发现队列扫描 starvation 和省略 episode_id 的 legacy 分镜图跨集提升风险，已处理；第六轮窄审确认 capped-scan starvation 已解决；第七轮发现 provider health 空白字符串可能误判 ready，已处理。付费 smoke 增量复审发现的重复提交、恢复阻塞和 unblock scope 问题均已处理，最终复审无 Critical/Important/Minor 遗留。

| 问题 | 修复 | 证据 |
| --- | --- | --- |
| scoped real worker 漏领 `target_type="episode"` 的专家自动修复 job | `_real_run_claimable_jobs_query` 同时支持生产剧集 id 和业务 Episode id；新增同 plan 不同剧集隔离测试 | `test_real_worker_step_claims_episode_repair_job_for_run_episode_scope` |
| 后台 `run_real_worker_queue_step` 未过滤 run 终态/审核态 | 普通 provider job 只扫描 `running/image_batch_running/video_batch_running/composing`；review/final-review 状态没有 repair job 时跳过，completed/failed/cancelled 始终跳过 | `test_real_worker_queue_step_skips_inactive_real_short_runs`, `test_real_worker_queue_step_processes_review_state_agency_repair_jobs` |
| 真实视频后台 worker 默认启动风险 | `REAL_VIDEO_WORKER_ENABLED` 改为显式 opt-in；未设置或 `0` 不启动，`true/1/yes/on` 才启动 | `test_real_video_background_worker_is_opt_in` |
| 缺少 `production_episode_id` 的 fallback 仍可能领取同 plan 任意专家自动修复 job | fallback 查询收紧为 `target_type="episode"` 且 `target_id == run.episode_id`；无作用域时不领取 segment repair | `test_real_worker_step_without_production_episode_scope_only_claims_own_episode_repair` |
| 后台队列跳过 review/final-review 状态下的专家修复 job | 队列扫描加入 repair-only 状态；review 状态只允许领取当前作用域的 `agency_auto_repair:%` job，不领取普通 provider job | `test_real_worker_queue_step_processes_review_state_agency_repair_jobs` |
| direct provider helper 缺少无 `agent_runner` 的 submit/query 证明 | 新增无 runner 的 mock direct 测试，验证 submit 无资产后继续 query 并返回资产结果；报告改称 agent-runner bypass，provider 工具仍经 worker/executor 闸门 | `test_provider_stage_agent_runs_mock_tools_directly_without_runner` |
| 分镜图提升报告措辞过强 | 报告改为拒绝显式跨 run/跨 episode，同时兼容同 episode 无 run_id 旧资产 | `test_storyboard_image_service.py` |
| 后台队列固定窗口空 review run 可能饿死 active run | 改为分页扫描候选 run 直到找到可处理任务或耗尽候选，并新增 1001 个空 review run 不阻塞 active run 的回归 | `test_real_worker_queue_step_does_not_starve_active_runs_behind_many_empty_review_runs` |
| API 省略 episode_id 时旧分镜图资产可能跨集提升 | promote 服务端从 run 读取 effective episode，并校验 asset/task context；新增 legacy nullable episode 回归 | `test_promote_storyboard_image_asset_rejects_legacy_asset_for_other_episode_when_episode_omitted` |
| 系统健康检查误判 Pixelle Compose 缺 `api_key/base_url` | 健康检查对 Pixelle 使用与真实提交路径一致的 `SystemSetting.pixelle_video_url/pixelle_api_key` 连接配置回退，避免 false blocked | `test_provider_capability_health_accepts_pixelle_settings_for_video_composition` |
| 系统健康检查可能把空白连接配置误判 ready | 连接配置和 model_name 判定改为 strip 后非空；Pixelle fallback 仅限 Pixelle provider，非 Pixelle 不继承 Pixelle settings | `test_provider_capability_health_treats_whitespace_connection_values_as_missing`, `test_provider_capability_health_does_not_apply_pixelle_settings_to_other_providers` |
| 付费 provider 欠费错误匹配过宽 | `access denied` 只有同时出现账务语义（`good standing`/`overdue`）才按额度/欠费处理；普通 API key 权限错误仍是 provider failure | `test_retryable_access_denied_without_billing_is_not_quota_failure` |
| 已失败 provider task 再同步时没有归档 idempotency key | terminal 早返回前也会幂等归档 key 并更新错误码，确保充值后能创建新 task 重试，不复用旧失败 task | `test_retryable_quota_existing_failed_task_archives_key_for_new_submit` |
| 付费 smoke 遇到欠费/额度阻塞后反复重试 | smoke 脚本遇到 `PROVIDER_THROTTLED`/`BUDGET_BLOCKED` 立即停止；恢复时若当前 run 作用域同阶段已有外部阻塞记录，worker 前直接停止；真实付费 smoke 强制 worker batch size 为 1；账户/预算修复后只能用显式 `--retry-provider-blockers` 清除当前 run 作用域同阶段 `retry_wait` blocker 后继续 | `test_paid_smoke_stage_stops_on_provider_billing_block`, `test_paid_smoke_stage_stops_before_worker_when_prior_provider_block_exists`, `test_paid_smoke_forces_single_worker_batch_for_paid_safety`, `test_paid_smoke_retry_provider_blockers_explicitly_unblocks_retry_wait_job` |
| 百炼 `wan2.6-image` 不能走旧 multimodal sync payload | 对 `dashscope_multimodal_generation` 中配置 `task_submit_path/task_query_path` 的模型改走 DashScope async image-generation，并在同步恢复时把资产 `provider_stage_task_id` 映射回内部 task id，避免外部 task id 外键写入失败 | `test_submit_image_batch_uses_dashscope_async_image_generation_when_configured`, `test_get_stage_task_returns_stored_provider_stage_summary_with_internal_task_id` |
| 百炼 `wan2.7-i2v` 视频接口拒绝旧 `input.img_url` | 视频直连 payload 改为 `input.media=[{"type":"first_frame","url":...}]`，保留 async task 查询和 provider task/idempotency 证据链 | `test_submit_video_batch_uses_dashscope_async_and_get_stage_task_queries` |
| 无本地 Pixelle 服务时最终合成无法进入终片审核 | 增加显式 `local_ffmpeg_compose` 协议；只有配置该协议时才用本地 ffmpeg concat 生成 `final_video` provider result，默认 Pixelle POST 路径不被静默替换；本地输入路径限制在项目视频输出和 Pixelle output 根内 | `test_submit_compose_uses_local_ffmpeg_protocol`, `test_local_ffmpeg_compose_rejects_paths_outside_controlled_outputs`, `test_compose_worker_persists_final_asset_before_final_audit` |
| 独立 review 发现 DashScope running summary 可能重启后永远不同步 | stored provider summary 只直接返回终态；非终态不再由本地 DB summary 伪装为 provider 同步结果，避免重启/跨进程后卡在 running | `test_get_stage_task_does_not_return_stored_running_summary` |
| 中文注释检查器漏检真实 provider submit 调用 | 高风险扫描补充 `.submit(`，`provider_stage_executor.py` 的真实付费提交行补中文边界注释，并扩展 keyword-only/variadic 参数契约检查 | `test_client_submit_requires_nearby_chinese_comment`, `test_python_function_contract_checks_keyword_and_variadic_parameters`, `test_all_business_code_has_standard_chinese_comments` |

## 当前验证命令

```powershell
server\.venv\Scripts\python.exe -m pytest -q
server\.venv\Scripts\python.exe -m pytest server/tests/test_system_health_page_contract.py -q
npx vitest run  # in web/
npm run build   # in web/
git diff --check
```

最近结果：

- 2026-06-23 当前全量重跑：后端 `.\.venv\Scripts\python.exe -m pytest -q`（在 `server/`）为 `1941 passed, 1 warning`；前端 `npx vitest run`（在 `web/`）为 `54 files / 350 tests passed`
- 后端全量：`1941 passed, 1 warning`
- 系统健康页契约：`11 passed`
- 真实付费 smoke 脚本合同：`test_bailian_smoke_script_contract.py` 覆盖 opt-in 参数、expert gate preflight、超时默认值、pending reference 衔接和 resume 跳过已完成阶段；无授权脚本调用安全退出并提示 `Set DY_AUTO_ALLOW_REAL_PROVIDER_E2E=1 to run paid provider smoke.`
- 弱证据补强批次：`test_video_production_start_flow_contract.py + test_script_pipeline.py` 为 `41 passed`；provider gate/job-spec 补强批次为 `71 passed`
- 核心函数组集合：`118 passed`
- Worker/一句话函数组集合：`79 passed`
- final gate/real_short mocked E2E：`18 passed`
- 多专家辩论/scorecard 本地 mocked/contract：`test_agency_debate_policy.py + test_agency_debate_audit.py + test_agency_scorecard_contracts.py` 为 `11 passed`
- 系统健康/设置/AI config/OSS helper 后端：`test_system_health_page_contract.py + test_settings_endpoints.py + test_ai_config*.py + test_system_operations_oss_service.py` 为 `56 passed`
- OSS helper 本地 fallback：`test_system_operations_oss_service.py` 为 `2 passed`
- 前端 AIConfigPage：`npx vitest run src/__tests__/ai-config-page.test.js` 为 `1 file / 1 test passed`
- ORM/smoke 脚本补充点名批次：`test_video_production_orm_boundary.py + test_ai_video_series_orm_boundary.py + test_ai_text_artifact_orm_boundary.py + test_agency_invocation_models.py + test_agency_console.py + test_image_production_orm_boundary.py + test_image_creation_models.py + test_model_configuration_orm_boundary.py + test_system_configuration_orm_boundary.py + test_production_audit_event_orm_boundary.py + test_script_output_orm_boundary.py + test_bailian_smoke_script_contract.py` 为 `66 passed, 1 warning`
- 前端配置 API client 补充批次：`api-clients.test.js + ai-config-page.test.js` 为 `2 files / 40 tests passed`
- 路由/API client 目标回归：后端 `test_video_production_api.py + test_ai_text_artifacts_api.py + test_storyboard_images_api.py + test_agency_api.py + test_settings_endpoints.py + test_system_health_page_contract.py` 为 `57 passed`；前端 `api-clients.test.js` 为 `1 file / 39 tests passed`
- mock scale scheduler 源文件补充点名：`test_mock_scale_scheduler_service.py` 为 `7 passed`
- 窄范围清单复核：AI 视频生产域、专家域、文本产物、分镜图、系统配置/健康、相关 ORM、真实 smoke 脚本、审查辅助脚本、核心前端入口共 `98` 个非空业务/入口文件（排除包标记 `__init__.py`），按相对路径或报告表述中的文件名点名/边界归类 `missing=0`
- 当前 diff 覆盖对账：`git diff --name-only --diff-filter=ACM` 加未跟踪文件中的文本变更共 `33` 个文件，排除本报告后均能在审查报告中按路径或文件名找到覆盖说明，`missing_mentions=0`
- 报告源码引用复核：反引号中的 Python/JS/Vue 文件引用按完整路径、短路径、文件名和 glob 解析均能命中当前仓库文件，`missing=0`
- 当前 diff 声明覆盖复核：本次生产源码 diff 新增/改动的 Python/JS/Vue 函数和类声明，按声明名、文件名或文件路径均能在报告中找到覆盖说明，`missing_mentions=0`
- 当前 diff 新增行风险扫描：生产代码新增行扫描 TODO/FIXME、调试输出、宽泛异常、sleep、provider submit、HTTP/shell 边界；命中项仅为 `main.py` 后台 worker 循环的 sleep/异常记录重试和 `check_chinese_comments.py` 的风险模式字符串，均有下方测试或注释检查器覆盖。
- 路由/API client 入口复核：AI 视频相关 FastAPI router 和前端 API client 的路由 decorator/client 调用所属文件均已在报告中覆盖，`missing_owner_files=0`
- 域内源码注释/边界复核：`check_chinese_comments.py` 对 AI 视频生产域、专家域、文本产物、分镜图、系统配置/健康共 `83` 个源码文件执行模块说明、声明契约和高风险调用扫描，`module_missing=0`、`risk_missing=0`、`declaration_missing=0`、`contract_missing=0`
- 报告证据文件存在性复核：当前报告中的后端 Python 测试、前端 test JS 文件和测试 glob 引用均可解析到真实文件或匹配结果，`missing=0`
- 中文注释检查器恢复回归：`test_chinese_comment_checker.py` 为 `24 passed`
- 中文注释检查器 + OSS helper 最小回归：`test_chinese_comment_checker.py + test_system_operations_oss_service.py` 为 `26 passed`
- 后台 worker 生命周期/真实视频 worker opt-in 回归：`test_style_lock_background_worker.py + test_device_operations_status_lifecycle.py` 为 `9 passed`
- 新增行风险扫描相关回归：`test_style_lock_background_worker.py + test_device_operations_status_lifecycle.py + test_chinese_comment_checker.py` 为 `33 passed`
- reviewer 修复回归集：`65 passed`，覆盖 worker/repair/background/creative patch/storyboard 第四、五轮回归
- 文本产物/分镜图/LangChain/status 批次：`87 passed`；LangChain provider 第四轮回归：`18 passed`
- LangChain/直接 HTTP 边界 inventory：`test_project_langchain_ai_inventory.py` 为 `8 passed`
- 系列策划/风格锁/状态批次：`94 passed`
- 前端文本追溯/系列详情/生产监控批次：`6 files / 108 tests passed`
- Provider executor/router/readiness 批次：`133 passed`
- 队列/成本/存储/审核/树/重试/状态支撑面批次：`115 passed`
- 覆盖审计补充：AI 视频相关源码/前端入口已在上方函数组和支撑模块表中逐项点名或边界归类；真实 provider E2E 以 2026-06-23 最新恢复完成记录为准
- 补充支撑模块后端批次：agency contracts/persistence/repair/multimodal、series read model、segment retry/status 共 `79 passed`
- 前端 console/list/API 补充批次：`4 files / 50 tests passed`
- 前端一句话/AI 审核/批量动作/API 支撑面批次：`7 files / 83 tests passed`
- 2026-06-23 全链路专项复核：一句话/系列后端链路 `test_one_sentence_video.py + test_one_sentence_video_run_types.py + test_series_planning_service.py + test_series_api.py + test_series_style_lock_pipeline.py + test_video_production_start_flow_contract.py` 为 `126 passed`；前端一句话/系列/API client 为 `6 files / 89 tests passed`；生产监控/run type/repair node 前端补充为 `5 files / 37 tests passed`
- 路由 HTTP 检查：`GET http://localhost:3000/series/f49718b7-e0ec-4012-b7fa-5c5229105d47/ai-text-artifacts` 返回 `200`
- 真实浏览器登录态检查：Playwright + 系统 Chrome 打开 `/series/f49718b7-e0ec-4012-b7fa-5c5229105d47/ai-text-artifacts`，page `200`，36 个文本产物匹配项，无 badResponses/requestfailed
- 前端全量：`54 files / 350 tests passed`
- 前端构建：通过，有 Vite 大 chunk 和 plugin timing 提示
- `/api/system/health`/provider capability 真实 provider 预检：`status=ok`，`paid_ready_count=3`，`worker_runtime_status=ok`，`image_generation=ok`，`video_rendering=ok`，`video_composition=ok`；Pixelle Compose 通过 `SystemSetting.pixelle_video_url/pixelle_api_key` 判定 ready，`latest_paid_smoke=null`
- 本轮健康接口刷新：`http://127.0.0.1:8001/health` 返回 `200 {"status":"ok","version":"0.3.0"}`；使用本地管理员登录获取鉴权令牌（未记录具体值）后，`/api/system/health` 返回 `200`，`status=ok`，`migration_status=ok`，`provider_capability_status=ok`，`worker_runtime_status=ok`，`paid_ready_count=3`，`image_generation/video_rendering/video_composition=ok`，`latest_paid_smoke=null`
- 阿里云百炼/DashScope 真实付费 smoke（2026-06-22）：`run_id=7a946c32-7362-461c-a45a-fc79bcf039da`，`series_id=bf0b870a-75d5-475f-9c0d-64681b4a2d74`。`qwen-image-2.0-pro` provider tasks `598c4225-e66b-45a5-b9fa-c09148e8805d`、`614a2f7d-b492-4f26-901c-85d90f8370c1` 均 `succeeded`，图片资产已持久化到 `server/output/video-production`；`wan2.7-i2v` task `478b8e41-d6ab-40a7-9cd9-44088163f3d6` `succeeded`，视频片段资产 `3752cdce-0c0a-4114-bfd6-3a6cc4108a7f.mp4`，`size_bytes=1906629`。第二个 `wan2.7-i2v` task `0042168e-9fec-422d-9d7e-c89d5020a955` 被 DashScope 拒绝：`HTTP 400 Access denied ... overdue-payment`；已将旧失败 task 归档，run 当前为 `video_batch_running/video_rendering`，剩余 job 为 `retry_wait/PROVIDER_THROTTLED`，最终 Pixelle Compose 未开始。
- 2026-06-23 同 run 恢复尝试：仍返回 `PROVIDER_THROTTLED`，随后因多次本地预留触发 `BUDGET_BLOCKED`；已按 0 成本结清本次失败重试产生的 12 个 stale reservation，run 恢复为 `video_batch_running/video_rendering`，剩余 job 为 `retry_wait/PROVIDER_THROTTLED`，plan `current_cost=0.55`。
- 2026-06-23 只读 DB/文件刷新：同一 `run_id` 仍为 `video_batch_running/video_rendering`、`completed_at=None`，plan 为 `running`、`budget_limit=5.0`、`current_cost=0.55`；production jobs 为 image `completed=2`、video `completed=1`、video `retry_wait/PROVIDER_THROTTLED=1`；provider task 历史为 `succeeded=3`、`failed/PROVIDER_THROTTLED=12`、`reserved=1`，15 条 reservation 均 `settled`；资产为 2 张 `image/approved/persisted`、1 段 `video_segment/review_pending/persisted`，`final_asset_count=0`，本地视频文件 `3752cdce-0c0a-4114-bfd6-3a6cc4108a7f.mp4` 仍存在且 `size_bytes=1906629`。
- 2026-06-23 当前只读 DB 复核：同一 `run_id=7a946c32-7362-461c-a45a-fc79bcf039da` 仍为 `run_status=video_batch_running`、`completed_at=None`、`run_type=real_short_e2e`；plan 仍为 `running`、`budget_limit=5.0`、`current_cost=0.55`；jobs 仍为 image `completed=2`、video `completed=1`、video `retry_wait/PROVIDER_THROTTLED=1`；provider tasks 仍为 image `succeeded=2`、video `succeeded=1`、video `failed/PROVIDER_THROTTLED=12`、video `reserved=1`；reservations `settled=15`；assets 仍为 2 张 `image/approved/persisted`、1 段 `video_segment/review_pending/persisted`，`final_asset_count=0`，本地视频 `3752cdce-0c0a-4114-bfd6-3a6cc4108a7f.mp4` 存在且 `size_bytes=1906629`。
- 2026-06-23 完成性审计刷新：同一 `run_id` 仍未完成，`status=video_batch_running`、`current_stage=video_rendering`、`completed_at=None`；plan 仍为 `running`、`current_cost=0.55`；jobs 仍为 image `completed=2`、video `completed=1`、video `retry_wait/PROVIDER_THROTTLED=1`；provider tasks 仍为 image `succeeded=2`、video `succeeded=1`、video `failed/PROVIDER_THROTTLED=12`、video `reserved=1`；assets 仍为 2 张 `image/approved`、1 段 `video_segment/review_pending`，`final_asset_count=0`，本地视频文件存在且 `size_bytes=1906629`。
- 2026-06-23 新百炼 key 恢复尝试：已把用户提供的新 key 写入本地加密模型配置并用同一 `run_id` 执行 `--retry-provider-blockers`；新建的 `wan2.7-i2v` provider task `488fd06a-9316-4b18-9330-7dddcebf7376` 可查询到 provider 结果，但结果资产为 `status=failed`、`error_code=VIDEO_RENDER_FAILED`，provider message 仍为 `HTTP 400 Access denied ... account is in good standing ... overdue-payment`。因此该 key 没有解除 DashScope 账户/计费阻塞；本轮未产生第二段成功视频，也未进入最终合成。当前 DB 状态为 run `image_batch_running/image_generation`、image repair job `retry_wait/PROVIDER_SUBMIT_FAILED=1`、video job `failed/PROVIDER_SUBMIT_FAILED=1`，资产仍为 2 张 `image/approved`、1 段 `video_segment/review_pending`，`final_asset_count=0`。
- 2026-06-23 最新恢复完成：同一 `run_id=7a946c32-7362-461c-a45a-fc79bcf039da` 在用户提供的免费额度视觉模型清单下切换本地测试配置后完成；jobs 为 `image_generation completed=3`、`video_generation completed=2`、`episode_compose completed=1`，provider tasks 为 `qwen-image-2.0-pro succeeded=2`、`wan2.6-image succeeded=1`、`wan2.7-i2v succeeded=2`、`local/ffmpeg-concat episode_compose succeeded=1`；资产为 3 张 `image/approved/persisted`、2 段 `video_segment/approved/persisted`、1 个 `final_video/approved/persisted`；最终 run `status=completed/current_stage=completed/completed_at=2026-06-23 16:50:50.675748`，final asset `e5afdb9b-43e6-4fc9-b075-a166292160e5`，文件 `server/output/video-production/e5afdb9b-43e6-4fc9-b075-a166292160e5.mp4`，`size_bytes=5189782`，checksum `ff37f8dba965bf6d597253dfa7c0d57b6369fe83a06766c0448dc26c5e86878a`。本条 supersede 上方“未进入最终合成/未完成”历史阻塞记录。
- 报告引用漂移复核：反查报告中的源码文件引用、路由/API owner 和可疑标识符引用；`mock_series_scale` 已确认是真实 run type/入口语义，`production_audit_events`、`system_settings`、`ai_models`、`scene_key`、`protocol`、`video_batch_running`、`retry_wait`、`asset_scope` 等疑似“缺失标识符”均为表名、字段名、状态值或前端局部变量，不是未审查的函数/类 owner。
- 后端和前端行级/声明级覆盖复核：`server\.venv\Scripts\python.exe server\scripts\check_ai_video_report_coverage.py --report docs\superpowers\reports\2026-06-22-ai-video-generation-code-review-audit.md`；按本报告范围扫描 AI 视频生产、剧集、文本产物、分镜图、专家团队、模型/系统配置、Pixelle、script pipeline、相关 ORM、`main.py`、真实 smoke 脚本、审查辅助脚本和前端 AI 视频主链路入口，共 `100` 个 Python 文件、`1279` 个 Python 函数/类声明、`16` 个前端文件、`367` 个前端声明，并校验 `302` 个报告文件引用和 `14` 个 Python pytest node 引用；`source_lines=35699`、`source_lines_covered=35699`、`missing_source_lines=0`、`python_covered=1279`、`frontend_covered=367`、`missing=0`、`missing_file_refs=0`、`missing_pytest_refs=0`。该 checker 是 owner/引用完整性防漏网，不单独证明每行语义已人工审查；语义结论以上方逐模块审查表、专项测试、真实 smoke 和独立 review 为准。
- 审查报告 checker 单元测试：`.\.venv\Scripts\python.exe -m pytest tests\test_ai_video_report_coverage_checker.py -q`（在 `server/`）为 `4 passed`
- 系列详情前端焦点回归：`npx vitest run src/__tests__/series-detail-agency.test.js src/__tests__/series-detail-video-production.test.js` -> `2 files / 37 tests passed`
- 支撑模块回归批次：`server\.venv\Scripts\python.exe -m pytest server/tests/test_agency_manifest.py server/tests/test_agency_runtime.py server/tests/test_agency_debate_policy.py server/tests/test_agency_debate_audit.py server/tests/test_ai_generator.py server/tests/test_ai_config.py server/tests/test_ai_config_resolve.py server/tests/test_ai_config_scene_schema.py server/tests/test_model_schema.py server/tests/test_model_registry.py server/tests/test_ai_model_migration.py server/tests/test_pixelle_client.py server/tests/test_pixelle_stage_client.py server/tests/test_pixelle_config_serialization.py server/tests/test_pixelle_config_security.py server/tests/test_image_creation_pixelle_client.py server/tests/test_script_pipeline.py server/tests/test_script_pipeline_provider_tools.py server/tests/test_pipeline_saved_storyboard_compat.py server/tests/test_script_pipeline_auth_parity.py server/tests/test_mock_scale_scheduler_service.py -q` -> `177 passed`
- DashScope/local compose/provider worker 回归批次：`server\.venv\Scripts\python.exe -m pytest tests\test_pixelle_stage_client.py tests\test_provider_stage_executor.py tests\test_video_production_real_worker_step.py tests\test_ai_video_langchain_provider_tools.py tests\test_ai_video_langchain_provider_stage_orchestrator.py -q` -> `89 passed`
- 付费 smoke/provider executor 修复回归：`server\.venv\Scripts\python.exe -m pytest tests\test_provider_stage_executor.py tests\test_bailian_smoke_script_contract.py -q` -> `43 passed`
- 付费 smoke 增量独立复审：初审 2 个 Important 已处理；第二轮指出 `--worker-batch-size > 1` 可能同批继续提交付费任务，已强制 paid smoke 单任务批处理并补回归；第三轮指出 `--retry-provider-blockers` 原按 plan/stage 清理过宽，已收窄到当前 run 的 production episode 作用域并补 sibling episode 回归；最终复审 `Critical: none / Important: none / Minor: none`
- 报告引用漂移独立复审：窄审确认新增引用漂移复核 bullet 无 Critical/Important/Minor，未泄露真实鉴权信息；历史付费阻塞记录已由 2026-06-23 最新恢复完成记录 supersede。
- 最终报告一致性独立复审：窄审确认当前只读 DB 复核、owner/引用完整性 checker、报告文件引用、pytest node 引用和真实 provider E2E 完成记录一致，`Critical: none / Important: none / Minor: none`；后续独立复审指出 blanket glob 不能作为逐行语义审查证明，本报告已改为 owner 边界归属口径。
- 敏感信息扫描：报告和本次源码 diff 未包含真实 API key、鉴权令牌值或签名媒体 URL；形态命中项经脱敏复核后仅为测试假 provider id
- `git diff --check`：无格式错误，仅 CRLF 提示
