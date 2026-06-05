import client from './client.js'

export function listImageProductionStrategies(params = {}) {
  return client.get('/image-production/strategies', { params })
}

export function createImageProductionStrategy(payload) {
  return client.post('/image-production/strategies', payload)
}

export function updateImageProductionStrategy(strategyId, payload) {
  return client.put(`/image-production/strategies/${strategyId}`, payload)
}

export function archiveImageProductionStrategy(strategyId) {
  return client.post(`/image-production/strategies/${strategyId}/archive`)
}

export function activateImageProductionStrategy(strategyId) {
  return client.post(`/image-production/strategies/${strategyId}/activate`)
}

export function refreshImageProductionMetrics(payload = {}) {
  return client.post('/image-production/strategies/metrics/refresh', payload)
}

export function getImageProductionStrategyRecommendations(strategyId) {
  return client.get(`/image-production/strategies/${strategyId}/recommendations`)
}

export function previewImageSelection(payload) {
  return client.post('/image-production/selection-preview', payload)
}

export function promoteImageAssetToVideo(assetId, payload) {
  return client.post(`/image-production/assets/${assetId}/promote-to-video-asset`, payload)
}

export function previewImageAbTest(payload) {
  return client.post('/image-production/ab-tests/preview', payload)
}

export function createImageAbTest(payload) {
  return client.post('/image-production/ab-tests', payload)
}

export function getImageAbTest(groupId) {
  return client.get(`/image-production/ab-tests/${groupId}`)
}

export function refreshImageAbTest(groupId) {
  return client.post(`/image-production/ab-tests/${groupId}/refresh`)
}

export function getImageAbWinnerRecommendation(groupId) {
  return client.get(`/image-production/ab-tests/${groupId}/winner-recommendation`)
}

export function chooseImageAbWinner(groupId, attemptId, payload) {
  return client.post(`/image-production/ab-tests/${groupId}/winner/${attemptId}`, payload)
}

export function chooseImageAbNoWinner(groupId, payload) {
  return client.post(`/image-production/ab-tests/${groupId}/no-winner`, payload)
}
