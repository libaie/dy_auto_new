/**
 * Seedance 2.0 API 客户端 — 通过 dy_auto 后端代理转发到火山方舟 Ark API.
 */
import axios from 'axios'

const proxy = axios.create({
  baseURL: '/api/seedance',
  timeout: 600000,
})

proxy.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 提交 Seedance 视频生成任务 (便捷端点) */
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 seedanceGenerate 对应业务流程的处理结果。
export function seedanceGenerate(payload) {
  return proxy.post('/generate', payload)
}

/** 查询 Seedance 任务状态 (便捷端点) */
// 入参：taskId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 seedanceGetTask 对应业务流程的处理结果。
export function seedanceGetTask(taskId) {
  return proxy.get(`/task/${taskId}`)
}
