// 前端 API 客户端：封装 videos 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listVideos(params = {}) {
  return client.get('/videos', { params })
}

// 前端业务函数：协调 getVideo 对应的页面流程、接口调用或状态转换。
export function getVideo(id) {
  return client.get(`/videos/${id}`)
}

// 前端业务函数：协调 deleteVideo 对应的页面流程、接口调用或状态转换。
export function deleteVideo(id) {
  return client.delete(`/videos/${id}`)
}

// 前端业务函数：协调 getVideoDownloadUrl 对应的页面流程、接口调用或状态转换。
export function getVideoDownloadUrl(id) {
  const token = localStorage.getItem('token') || ''
  return `/api/videos/${id}/download?token=${encodeURIComponent(token)}`
}
