// 前端 API 客户端：封装 tasks 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listTasks(params = {}) {
  return client.get('/tasks', { params })
}

// 前端业务函数：协调 createTask 对应的页面流程、接口调用或状态转换。
export function createTask(data) {
  return client.post('/tasks', data)
}

// 前端业务函数：协调 batchCreateTasks 对应的页面流程、接口调用或状态转换。
export function batchCreateTasks(data) {
  return client.post('/tasks/batch', data)
}

// 前端业务函数：协调 cancelTask 对应的页面流程、接口调用或状态转换。
export function cancelTask(id) {
  return client.post(`/tasks/${id}/cancel`)
}

// 前端业务函数：协调 deleteTask 对应的页面流程、接口调用或状态转换。
export function deleteTask(id) {
  return client.delete(`/tasks/${id}`)
}

// 前端业务函数：协调 batchDeleteTasks 对应的页面流程、接口调用或状态转换。
export function batchDeleteTasks(taskIds) {
  return client.post('/tasks/batch-delete', { task_ids: taskIds })
}
