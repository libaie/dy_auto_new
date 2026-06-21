// 前端 API 客户端：封装 videos 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listVideos(params = {}) {
  return client.get('/videos', { params })
}

export function getVideo(id) {
  return client.get(`/videos/${id}`)
}

export function deleteVideo(id) {
  return client.delete(`/videos/${id}`)
}

export function getVideoDownloadUrl(id) {
  const token = localStorage.getItem('token') || ''
  return `/api/videos/${id}/download?token=${encodeURIComponent(token)}`
}
