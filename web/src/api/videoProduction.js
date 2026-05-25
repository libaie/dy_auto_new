import client from './client.js'

export function createVideoProductionRun(seriesId, episodeId) {
  return client.post('/video-production/runs', {
    series_id: seriesId,
    episode_id: episodeId,
  })
}

export function getVideoProductionRun(runId) {
  return client.get(`/video-production/runs/${runId}`)
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
