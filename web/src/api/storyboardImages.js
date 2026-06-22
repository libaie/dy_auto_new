// 前端 API 客户端：封装 storyboardImages 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：episodeId、frameId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createStoryboardFrameImageTask 对应业务流程的处理结果。
export function createStoryboardFrameImageTask(episodeId, frameId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/frames/${frameId}/tasks`, payload)
}

// 前端业务函数：协调 createMissingStoryboardImageTasks 对应的页面流程、接口调用或状态转换。
// 入参：episodeId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createMissingStoryboardImageTasks 对应业务流程的处理结果。
export function createMissingStoryboardImageTasks(episodeId, payload) {
  return client.post(`/storyboard-images/episodes/${episodeId}/tasks:batch`, payload)
}

// 前端业务函数：协调 getStoryboardImageState 对应的页面流程、接口调用或状态转换。
// 入参：episodeId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getStoryboardImageState 对应业务流程的处理结果。
export function getStoryboardImageState(episodeId, params = {}) {
  return client.get(`/storyboard-images/episodes/${episodeId}`, { params })
}

// 前端业务函数：协调 promoteStoryboardImageAsset 对应的页面流程、接口调用或状态转换。
// 入参：assetId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 promoteStoryboardImageAsset 对应业务流程的处理结果。
export function promoteStoryboardImageAsset(assetId, payload) {
  return client.post(`/storyboard-images/assets/${assetId}/promote`, payload)
}
