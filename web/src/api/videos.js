// 前端 API 客户端：封装 videos 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listVideos 对应业务流程的处理结果。
export function listVideos(params = {}) {
  return client.get('/videos', { params })
}

// 前端业务函数：协调 getVideo 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getVideo 对应业务流程的处理结果。
export function getVideo(id) {
  return client.get(`/videos/${id}`)
}

// 前端业务函数：协调 deleteVideo 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteVideo 对应业务流程的处理结果。
export function deleteVideo(id) {
  return client.delete(`/videos/${id}`)
}

// 前端业务函数：协调 getVideoDownloadUrl 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getVideoDownloadUrl 对应业务流程的处理结果。
export function getVideoDownloadUrl(id) {
  const token = localStorage.getItem('token') || ''
  return `/api/videos/${id}/download?token=${encodeURIComponent(token)}`
}
