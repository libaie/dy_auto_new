/**
 * Pixelle-Video API 客户端 — 通过 dy_auto 后端透明代理转发到 Pixelle-Video 服务。
 *
 * 所有请求走 /api/pixelle-proxy/{path}，后端根据 SystemSetting 中的
 * pixelle_video_url 将请求透明转发到 Pixelle-Video 的 FastAPI 服务。
 */
import axios from 'axios'

const proxy = axios.create({
  baseURL: '/api/pixelle-proxy',
  timeout: 600000, // 视频生成可能需要 10 分钟
})

// Attach JWT Bearer token (same pattern as api/client.js)
proxy.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ==================== 视频生成 ====================

// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateVideoAsync 对应业务流程的处理结果。
export function generateVideoAsync(payload) {
  return proxy.post('/api/video/generate/async', payload)
}

// 前端业务函数：协调 generateVideoSync 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateVideoSync 对应业务流程的处理结果。
export function generateVideoSync(payload) {
  return proxy.post('/api/video/generate/sync', payload)
}

// ==================== 任务管理 ====================

// 入参：taskId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getTask 对应业务流程的处理结果。
export function getTask(taskId) {
  return proxy.get(`/api/tasks/${taskId}`)
}

// 前端业务函数：协调 listTasks 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listTasks 对应业务流程的处理结果。
export function listTasks() {
  return proxy.get('/api/tasks')
}

// ==================== 资源 ====================

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listTemplates 对应业务流程的处理结果。
export function listTemplates() {
  return proxy.get('/api/resources/templates')
}

// 前端业务函数：协调 listMediaWorkflows 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listMediaWorkflows 对应业务流程的处理结果。
export function listMediaWorkflows() {
  return proxy.get('/api/resources/workflows/media')
}

// 前端业务函数：协调 listTTSWorkflows 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listTTSWorkflows 对应业务流程的处理结果。
export function listTTSWorkflows() {
  return proxy.get('/api/resources/workflows/tts')
}

// 前端业务函数：协调 listImageWorkflows 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listImageWorkflows 对应业务流程的处理结果。
export function listImageWorkflows() {
  return proxy.get('/api/resources/workflows/image')
}

// 前端业务函数：协调 listBGMs 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listBGMs 对应业务流程的处理结果。
export function listBGMs() {
  return proxy.get('/api/resources/bgm')
}

// 前端业务函数：协调 renderFrame 对应的页面流程、接口调用或状态转换。
// 入参：template、text 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 renderFrame 对应业务流程的处理结果。
export function renderFrame(template, text) {
  return proxy.post('/api/frame/render', { template, text })
}

// 前端业务函数：协调 getOpenAPISpec 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getOpenAPISpec 对应业务流程的处理结果。
export function getOpenAPISpec() {
  return proxy.get('/openapi.json')
}

// ==================== 内容生成 (AI) ====================

// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateNarration 对应业务流程的处理结果。
export function generateNarration(payload) {
  return proxy.post('/api/content/narration', payload)
}

// 前端业务函数：协调 generateImagePrompt 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateImagePrompt 对应业务流程的处理结果。
export function generateImagePrompt(payload) {
  return proxy.post('/api/content/image-prompt', payload)
}

// 前端业务函数：协调 generateTitle 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateTitle 对应业务流程的处理结果。
export function generateTitle(payload) {
  return proxy.post('/api/content/title', payload)
}

// ==================== TTS ====================

// 前端业务函数：协调 synthesizeTTS 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 synthesizeTTS 对应业务流程的处理结果。
export function synthesizeTTS(payload) {
  return proxy.post('/api/tts/synthesize', payload)
}

// ==================== 图像生成 ====================

// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateImage 对应业务流程的处理结果。
export function generateImage(payload) {
  return proxy.post('/api/image/generate', payload)
}

// ==================== 文件上传（BGM / 参考音频） ====================

// 入参：formData 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 uploadFile 对应业务流程的处理结果。
export function uploadFile(formData) {
  return proxy.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ==================== 获取视频文件 URL ====================

// 入参：videoPath 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getVideoFileUrl 对应业务流程的处理结果。
export function getVideoFileUrl(videoPath) {
  // Pixelle-Video serves files at GET /api/files/{file_path}
  if (!videoPath) return ''
  const encoded = encodeURIComponent(videoPath)
  return `/api/pixelle-proxy/api/files/${encoded}`
}
