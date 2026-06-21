// 前端 API 客户端：封装 videoProduction 相关后端接口，统一给页面和组件调用。
import client from './client.js'

const DEFAULT_TREE_PAGE = 1
const DEFAULT_TREE_PAGE_SIZE = 50
const MAX_TREE_PAGE_SIZE = 100

// 前端业务函数：协调 toBoundedPositiveInteger 对应的页面流程、接口调用或状态转换。
function toBoundedPositiveInteger(value, fallback, max = Number.MAX_SAFE_INTEGER) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue) || numberValue < 1) return fallback
  return Math.min(Math.floor(numberValue), max)
}

// 前端业务函数：协调 boundedTreeParams 对应的页面流程、接口调用或状态转换。
function boundedTreeParams(params = {}) {
  return {
    ...params,
    page: toBoundedPositiveInteger(params.page, DEFAULT_TREE_PAGE),
    page_size: toBoundedPositiveInteger(params.page_size, DEFAULT_TREE_PAGE_SIZE, MAX_TREE_PAGE_SIZE),
  }
}

// 前端业务函数：协调 createVideoProductionRun 对应的页面流程、接口调用或状态转换。
export function createVideoProductionRun(seriesId, episodeId) {
  return client.post('/video-production/runs', {
    series_id: seriesId,
    episode_id: episodeId,
  })
}

// 前端业务函数：协调 startEpisodeProduction 对应的页面流程、接口调用或状态转换。
export function startEpisodeProduction({
  series_id,
  episode_id,
  target_duration_seconds,
  budget_limit,
  autostart_images = true,
  run_type = 'real_short_e2e',
  auto_repair_policy,
}) {
  const resolvedBudget = budget_limit ?? (run_type === 'real_short_e2e' ? 1 : undefined)
  return client.post('/video-production/runs/start', {
    series_id,
    episode_id,
    target_duration_seconds,
    budget_limit: resolvedBudget,
    autostart_images,
    run_type,
    auto_repair_policy,
  })
}

// 前端业务函数：协调 createOneSentenceVideo 对应的页面流程、接口调用或状态转换。
export function createOneSentenceVideo({
  prompt,
  title,
  genre,
  target_duration_seconds = 60,
  budget_limit,
  autostart_images = true,
  run_type = 'real_short_e2e',
  auto_repair_policy,
}) {
  const resolvedBudget = budget_limit ?? (run_type === 'real_short_e2e' ? 1 : undefined)
  return client.post('/video-production/one-sentence', {
    prompt,
    title,
    genre,
    target_duration_seconds,
    budget_limit: resolvedBudget,
    autostart_images,
    run_type,
    auto_repair_policy,
  })
}

// 前端业务函数：协调 getVideoProductionRun 对应的页面流程、接口调用或状态转换。
export function getVideoProductionRun(runId) {
  return client.get(`/video-production/runs/${runId}`)
}

// 前端业务函数：协调 backfillRunTextArtifacts 对应的页面流程、接口调用或状态转换。
export function backfillRunTextArtifacts(runId) {
  return client.post(`/video-production/runs/${runId}/backfill-text-artifacts`)
}

// 前端业务函数：协调 getRunReadiness 对应的页面流程、接口调用或状态转换。
export function getRunReadiness(runId) {
  return client.get(`/video-production/runs/${runId}/readiness`)
}

// 前端业务函数：协调 runMockSchedulerStep 对应的页面流程、接口调用或状态转换。
export function runMockSchedulerStep(runId, payload = {}) {
  return client.post(`/video-production/runs/${runId}/mock-worker-step`, {
    lease_id: 'ui-worker',
    batch_size: 1,
    ...payload,
  })
}

// 前端业务函数：协调 runRealWorkerStep 对应的页面流程、接口调用或状态转换。
export function runRealWorkerStep(runId, payload = {}) {
  return client.post(`/video-production/runs/${runId}/worker-step`, {
    lease_id: 'ui-real-worker',
    batch_size: 1,
    ...payload,
  })
}

// 前端业务函数：协调 startImageStage 对应的页面流程、接口调用或状态转换。
export function startImageStage(runId) {
  return client.post(`/video-production/runs/${runId}/start-images`)
}

// 前端业务函数：协调 syncImageStage 对应的页面流程、接口调用或状态转换。
export function syncImageStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-image-results`)
}

// 前端业务函数：协调 listReviewItems 对应的页面流程、接口调用或状态转换。
export function listReviewItems(params = {}) {
  return client.get('/video-production/review-items', { params })
}

// 前端业务函数：协调 reviewAsset 对应的页面流程、接口调用或状态转换。
export function reviewAsset(assetId, action, comment = '') {
  return client.post(`/video-production/assets/${assetId}/review`, { action, comment })
}

// 前端业务函数：协调 regenerateAsset 对应的页面流程、接口调用或状态转换。
export function regenerateAsset(assetId, payload) {
  return client.post(`/video-production/assets/${assetId}/regenerate`, payload)
}

// 前端业务函数：协调 voidProductionAsset 对应的页面流程、接口调用或状态转换。
export function voidProductionAsset(assetId, payload = {}) {
  return client.post(`/video-production/assets/${assetId}/void`, payload)
}

// 前端业务函数：协调 imageEditProductionAsset 对应的页面流程、接口调用或状态转换。
export function imageEditProductionAsset(assetId, payload) {
  return client.post(`/video-production/assets/${assetId}/image-edit`, payload)
}

// 前端业务函数：协调 startVideoStage 对应的页面流程、接口调用或状态转换。
export function startVideoStage(runId) {
  return client.post(`/video-production/runs/${runId}/start-videos`)
}

// 前端业务函数：协调 syncVideoStage 对应的页面流程、接口调用或状态转换。
export function syncVideoStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-video-results`)
}

// 前端业务函数：协调 startComposeStage 对应的页面流程、接口调用或状态转换。
export function startComposeStage(runId) {
  return client.post(`/video-production/runs/${runId}/compose`)
}

// 前端业务函数：协调 syncComposeStage 对应的页面流程、接口调用或状态转换。
export function syncComposeStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-compose-results`)
}

// 前端业务函数：协调 startAssetRegeneration 对应的页面流程、接口调用或状态转换。
export function startAssetRegeneration(assetId) {
  return client.post(`/video-production/assets/${assetId}/start-regeneration`)
}

// 前端业务函数：协调 syncAssetRegeneration 对应的页面流程、接口调用或状态转换。
export function syncAssetRegeneration(assetId) {
  return client.post(`/video-production/assets/${assetId}/sync-regeneration`)
}

// 前端业务函数：协调 retryAssetPersistence 对应的页面流程、接口调用或状态转换。
export function retryAssetPersistence(assetId) {
  return client.post(`/video-production/assets/${assetId}/persist-retry`)
}

// 前端业务函数：协调 getProductionTree 对应的页面流程、接口调用或状态转换。
export function getProductionTree(planId, params = {}) {
  return client.get(`/video-production/plans/${planId}/tree`, { params: boundedTreeParams(params) })
}

// 前端业务函数：协调 getRunProductionTree 对应的页面流程、接口调用或状态转换。
export function getRunProductionTree(runId, params = {}) {
  return client.get(`/video-production/runs/${runId}/tree`, { params: boundedTreeParams(params) })
}

// 前端业务函数：协调 getSegmentDetail 对应的页面流程、接口调用或状态转换。
export function getSegmentDetail(segmentId, params = {}) {
  return client.get(`/video-production/segments/${segmentId}/detail`, { params })
}

// 前端业务函数：协调 getProviderStageTasks 对应的页面流程、接口调用或状态转换。
export function getProviderStageTasks(runId, params = {}) {
  return client.get(`/video-production/runs/${runId}/provider-stage-tasks`, { params: boundedTreeParams(params) })
}

// 前端业务函数：协调 getSegmentRetryImpact 对应的页面流程、接口调用或状态转换。
export function getSegmentRetryImpact(segmentId) {
  return client.get(`/video-production/segments/${segmentId}/retry-impact`)
}

// 前端业务函数：协调 getRunCosts 对应的页面流程、接口调用或状态转换。
export function getRunCosts(runId) {
  return client.get(`/video-production/runs/${runId}/costs`)
}

// 前端业务函数：协调 retryProductionSegment 对应的页面流程、接口调用或状态转换。
export function retryProductionSegment(segmentId) {
  return client.post(`/video-production/segments/${segmentId}/retry`)
}

// 前端业务函数：协调 pauseProductionRun 对应的页面流程、接口调用或状态转换。
export function pauseProductionRun(runId) {
  return client.post(`/video-production/runs/${runId}/pause`)
}

// 前端业务函数：协调 resumeProductionRun 对应的页面流程、接口调用或状态转换。
export function resumeProductionRun(runId) {
  return client.post(`/video-production/runs/${runId}/resume`)
}

// 前端业务函数：协调 bulkReviewProductionAssets 对应的页面流程、接口调用或状态转换。
export function bulkReviewProductionAssets(payload) {
  return client.post('/video-production/reviews/bulk-action', payload)
}

// 前端业务函数：协调 createVideoCollection 对应的页面流程、接口调用或状态转换。
export function createVideoCollection(seriesId) {
  return client.post('/video-production/collections', { series_id: seriesId })
}
