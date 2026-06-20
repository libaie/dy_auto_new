import client from './client.js'

export function createStoryboardFrameImageTask(episodeId, frameId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/frames/${frameId}/tasks`, payload)
}

export function createMissingStoryboardImageTasks(episodeId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/tasks:batch`, payload)
}

export function getStoryboardImageState(episodeId, params = {}) {
  return client.get(`/storyboard-images/episodes/${episodeId}`, { params })
}

export function promoteStoryboardImageAsset(assetId, payload) {
  return client.post(`/storyboard-images/assets/${assetId}/promote`, payload)
}
