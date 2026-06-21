// 前端 API 客户端：封装 tasks 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listTasks(params = {}) {
  return client.get('/tasks', { params })
}

export function createTask(data) {
  return client.post('/tasks', data)
}

export function batchCreateTasks(data) {
  return client.post('/tasks/batch', data)
}

export function cancelTask(id) {
  return client.post(`/tasks/${id}/cancel`)
}

export function deleteTask(id) {
  return client.delete(`/tasks/${id}`)
}

export function batchDeleteTasks(taskIds) {
  return client.post('/tasks/batch-delete', { task_ids: taskIds })
}
