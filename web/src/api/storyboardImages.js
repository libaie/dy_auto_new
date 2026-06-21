// 前端 API 客户端：封装 storyboardImages 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function createStoryboardFrameImageTask(episodeId, frameId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/frames/${frameId}/tasks`, payload)
}

// 前端业务函数：协调 createMissingStoryboardImageTasks 对应的页面流程、接口调用或状态转换。
export function createMissingStoryboardImageTasks(episodeId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/tasks:batch`, payload)
}

// 前端业务函数：协调 getStoryboardImageState 对应的页面流程、接口调用或状态转换。
export function getStoryboardImageState(episodeId, params = {}) {
  return client.get(`/storyboard-images/episodes/${episodeId}`, { params })
}

// 前端业务函数：协调 promoteStoryboardImageAsset 对应的页面流程、接口调用或状态转换。
export function promoteStoryboardImageAsset(assetId, payload) {
  return client.post(`/storyboard-images/assets/${assetId}/promote`, payload)
}
