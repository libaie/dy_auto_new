import client from './client.js'

const DEFAULT_TREE_PAGE = 1
const DEFAULT_TREE_PAGE_SIZE = 50
const MAX_TREE_PAGE_SIZE = 100

function toBoundedPositiveInteger(value, fallback, max = Number.MAX_SAFE_INTEGER) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue) || numberValue < 1) return fallback
  return Math.min(Math.floor(numberValue), max)
}

function boundedTreeParams(params = {}) {
  return {
    ...params,
    page: toBoundedPositiveInteger(params.page, DEFAULT_TREE_PAGE),
    page_size: toBoundedPositiveInteger(params.page_size, DEFAULT_TREE_PAGE_SIZE, MAX_TREE_PAGE_SIZE),
  }
}

export function createVideoProductionRun(seriesId, episodeId) {
  return client.post('/video-production/runs', {
    series_id: seriesId,
    episode_id: episodeId,
  })
}

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

export function getVideoProductionRun(runId) {
  return client.get(`/video-production/runs/${runId}`)
}

export function backfillRunTextArtifacts(runId) {
  return client.post(`/video-production/runs/${runId}/backfill-text-artifacts`)
}

export function getRunReadiness(runId) {
  return client.get(`/video-production/runs/${runId}/readiness`)
}

export function runMockSchedulerStep(runId, payload = {}) {
  return client.post(`/video-production/runs/${runId}/mock-worker-step`, {
    lease_id: 'ui-worker',
    batch_size: 1,
    ...payload,
  })
}

export function runRealWorkerStep(runId, payload = {}) {
  return client.post(`/video-production/runs/${runId}/worker-step`, {
    lease_id: 'ui-real-worker',
    batch_size: 1,
    ...payload,
  })
}

export function startImageStage(runId) {
  return client.post(`/video-production/runs/${runId}/start-images`)
}

export function syncImageStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-image-results`)
}

export function listReviewItems(params = {}) {
  return client.get('/video-production/review-items', { params })
}

export function reviewAsset(assetId, action, comment = '') {
  return client.post(`/video-production/assets/${assetId}/review`, { action, comment })
}

export function regenerateAsset(assetId, payload) {
  return client.post(`/video-production/assets/${assetId}/regenerate`, payload)
}

export function voidProductionAsset(assetId, payload = {}) {
  return client.post(`/video-production/assets/${assetId}/void`, payload)
}

export function imageEditProductionAsset(assetId, payload) {
  return client.post(`/video-production/assets/${assetId}/image-edit`, payload)
}

export function startVideoStage(runId) {
  return client.post(`/video-production/runs/${runId}/start-videos`)
}

export function syncVideoStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-video-results`)
}

export function startComposeStage(runId) {
  return client.post(`/video-production/runs/${runId}/compose`)
}

export function syncComposeStage(runId) {
  return client.post(`/video-production/runs/${runId}/sync-compose-results`)
}

export function startAssetRegeneration(assetId) {
  return client.post(`/video-production/assets/${assetId}/start-regeneration`)
}

export function syncAssetRegeneration(assetId) {
  return client.post(`/video-production/assets/${assetId}/sync-regeneration`)
}

export function retryAssetPersistence(assetId) {
  return client.post(`/video-production/assets/${assetId}/persist-retry`)
}

export function getProductionTree(planId, params = {}) {
  return client.get(`/video-production/plans/${planId}/tree`, { params: boundedTreeParams(params) })
}

export function getRunProductionTree(runId, params = {}) {
  return client.get(`/video-production/runs/${runId}/tree`, { params: boundedTreeParams(params) })
}

export function getSegmentDetail(segmentId, params = {}) {
  return client.get(`/video-production/segments/${segmentId}/detail`, { params })
}

export function getProviderStageTasks(runId, params = {}) {
  return client.get(`/video-production/runs/${runId}/provider-stage-tasks`, { params: boundedTreeParams(params) })
}

export function getSegmentRetryImpact(segmentId) {
  return client.get(`/video-production/segments/${segmentId}/retry-impact`)
}

export function getRunCosts(runId) {
  return client.get(`/video-production/runs/${runId}/costs`)
}

export function retryProductionSegment(segmentId) {
  return client.post(`/video-production/segments/${segmentId}/retry`)
}

export function pauseProductionRun(runId) {
  return client.post(`/video-production/runs/${runId}/pause`)
}

export function resumeProductionRun(runId) {
  return client.post(`/video-production/runs/${runId}/resume`)
}

export function bulkReviewProductionAssets(payload) {
  return client.post('/video-production/reviews/bulk-action', payload)
}

export function createVideoCollection(seriesId) {
  return client.post('/video-production/collections', { series_id: seriesId })
}
