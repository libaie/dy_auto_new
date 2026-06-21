// 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。
import {
  generateVideoAsync,
  getTask,
  getVideoFileUrl,
  uploadFile,
} from '../../api/pixelle-client.js'

const COMPLETED_STATUSES = new Set(['completed', 'succeeded', 'success', 'done'])
const FAILED_STATUSES = new Set(['failed', 'error'])

function uploadResponsePath(data) {
  const payload = data?.data && typeof data.data === 'object' ? data.data : data
  if (!payload || typeof payload !== 'object') return ''
  for (const key of ['path', 'file_path', 'filepath', 'url', 'file_url', 'local_path', 'storage_path']) {
    if (payload[key]) return String(payload[key])
  }
  if (payload.file && typeof payload.file === 'object') return uploadResponsePath(payload.file)
  if (Array.isArray(payload.files) && payload.files.length) return uploadResponsePath(payload.files[0])
  return ''
}

export async function uploadPixelleFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await uploadFile(formData)
  const path = uploadResponsePath(resp.data)
  if (!path) throw new Error(`上传失败：${file?.name || '文件'} 未返回可用路径`)
  return path
}

export async function uploadPixelleFiles(files) {
  const results = []
  for (const file of Array.from(files || [])) {
    results.push(await uploadPixelleFile(file))
  }
  return results
}

function videoUrlFromTask(data) {
  const direct = data.video_url || data.url
  if (direct) return String(direct)
  const path = data.video_path || data.final_video_path || data.file_path
  return path ? getVideoFileUrl(path) : ''
}

function taskResult(taskId, data) {
  const videoPath = data.video_path || data.final_video_path || data.file_path || data.video_url || data.url || ''
  return {
    success: true,
    taskId,
    duration: data.duration,
    fileSize: data.file_size,
    frames: data.frames,
    videoPath,
    videoUrl: videoUrlFromTask(data),
  }
}

export async function runPixelleVideoGeneration(payload, options = {}) {
  const {
    intervalMs = 5000,
    maxAttempts = 120,
    onProgress,
  } = options

  const resp = await generateVideoAsync(payload)
  const taskId = resp.data?.task_id
  if (!taskId) throw new Error('No task ID')

  return await new Promise((resolve, reject) => {
    let attempts = 0
    const timer = setInterval(async () => {
      attempts += 1
      if (attempts > maxAttempts) {
        clearInterval(timer)
        reject(new Error('Timeout'))
        return
      }

      try {
        const r = await getTask(taskId)
        const data = r.data || {}
        const status = String(data.status || '').toLowerCase()
        if (COMPLETED_STATUSES.has(status)) {
          clearInterval(timer)
          resolve(taskResult(taskId, data))
          return
        }
        if (FAILED_STATUSES.has(status)) {
          clearInterval(timer)
          reject(new Error(data.error || 'Pixelle-Video 返回失败'))
          return
        }
        const percent = data.progress != null ? Math.min(95, data.progress) : undefined
        onProgress?.({
          percent,
          message: data.stage || data.status || 'running',
        })
      } catch {
        if (attempts % 6 === 0) {
          onProgress?.({ message: `网络波动，重试中... (${attempts}/${maxAttempts})` })
        }
      }
    }, intervalMs)
  })
}
