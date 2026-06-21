// 前端 API 客户端：封装 imageCreation 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function uploadImageSource(formData) {
  return client.post('/image-creation/uploads', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function createImageTask(payload) {
  return client.post('/image-creation/tasks', payload)
}

export function getImageTask(taskId) {
  return client.get(`/image-creation/tasks/${taskId}`)
}

export function syncImageTask(taskId) {
  return client.post(`/image-creation/tasks/${taskId}/sync`)
}

export function dispatchQueuedImageTask(taskId) {
  return client.post(`/image-creation/tasks/${taskId}/dispatch`)
}

export function listImageAssets(params = {}) {
  return client.get('/image-creation/assets', { params })
}

export function reviewImageAsset(assetId, payload) {
  return client.post(`/image-creation/assets/${assetId}/review`, payload)
}

export function editImageAsset(assetId, payload) {
  return client.post(`/image-creation/assets/${assetId}/edit`, payload)
}
