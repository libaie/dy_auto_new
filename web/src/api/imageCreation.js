// 前端 API 客户端：封装 imageCreation 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function uploadImageSource(formData) {
  return client.post('/image-creation/uploads', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 前端业务函数：协调 createImageTask 对应的页面流程、接口调用或状态转换。
export function createImageTask(payload) {
  return client.post('/image-creation/tasks', payload)
}

// 前端业务函数：协调 getImageTask 对应的页面流程、接口调用或状态转换。
export function getImageTask(taskId) {
  return client.get(`/image-creation/tasks/${taskId}`)
}

// 前端业务函数：协调 syncImageTask 对应的页面流程、接口调用或状态转换。
export function syncImageTask(taskId) {
  return client.post(`/image-creation/tasks/${taskId}/sync`)
}

// 前端业务函数：协调 dispatchQueuedImageTask 对应的页面流程、接口调用或状态转换。
export function dispatchQueuedImageTask(taskId) {
  return client.post(`/image-creation/tasks/${taskId}/dispatch`)
}

// 前端业务函数：协调 listImageAssets 对应的页面流程、接口调用或状态转换。
export function listImageAssets(params = {}) {
  return client.get('/image-creation/assets', { params })
}

// 前端业务函数：协调 reviewImageAsset 对应的页面流程、接口调用或状态转换。
export function reviewImageAsset(assetId, payload) {
  return client.post(`/image-creation/assets/${assetId}/review`, payload)
}

// 前端业务函数：协调 editImageAsset 对应的页面流程、接口调用或状态转换。
export function editImageAsset(assetId, payload) {
  return client.post(`/image-creation/assets/${assetId}/edit`, payload)
}
