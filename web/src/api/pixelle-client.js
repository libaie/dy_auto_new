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

export function generateVideoAsync(payload) {
  return proxy.post('/api/video/generate/async', payload)
}

export function generateVideoSync(payload) {
  return proxy.post('/api/video/generate/sync', payload)
}

// ==================== 任务管理 ====================

export function getTask(taskId) {
  return proxy.get(`/api/tasks/${taskId}`)
}

export function listTasks() {
  return proxy.get('/api/tasks')
}

// ==================== 资源 ====================

export function listTemplates() {
  return proxy.get('/api/resources/templates')
}

export function listMediaWorkflows() {
  return proxy.get('/api/resources/workflows/media')
}

export function listTTSWorkflows() {
  return proxy.get('/api/resources/workflows/tts')
}

export function listImageWorkflows() {
  return proxy.get('/api/resources/workflows/image')
}

export function listBGMs() {
  return proxy.get('/api/resources/bgm')
}

export function renderFrame(template, text) {
  return proxy.post('/api/frame/render', { template, text })
}

export function getOpenAPISpec() {
  return proxy.get('/openapi.json')
}

// ==================== 内容生成 (AI) ====================

export function generateNarration(payload) {
  return proxy.post('/api/content/narration', payload)
}

export function generateImagePrompt(payload) {
  return proxy.post('/api/content/image-prompt', payload)
}

export function generateTitle(payload) {
  return proxy.post('/api/content/title', payload)
}

// ==================== TTS ====================

export function synthesizeTTS(payload) {
  return proxy.post('/api/tts/synthesize', payload)
}

// ==================== 图像生成 ====================

export function generateImage(payload) {
  return proxy.post('/api/image/generate', payload)
}

// ==================== 文件上传（BGM / 参考音频） ====================

export function uploadFile(formData) {
  return proxy.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ==================== 获取视频文件 URL ====================

export function getVideoFileUrl(videoPath) {
  // Pixelle-Video serves files at GET /api/files/{file_path}
  if (!videoPath) return ''
  const encoded = encodeURIComponent(videoPath)
  return `/api/pixelle-proxy/api/files/${encoded}`
}
