// 前端 API 客户端：封装 dmSequences 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listDMSequences(params = {}) {
  return client.get('/dm-sequences', params)
}

// 前端业务函数：协调 getDMSequence 对应的页面流程、接口调用或状态转换。
export function getDMSequence(id) {
  return client.get(`/dm-sequences/${id}`)
}

// 前端业务函数：协调 createDMSequence 对应的页面流程、接口调用或状态转换。
export function createDMSequence(data) {
  return client.post('/dm-sequences', data)
}

// 前端业务函数：协调 updateDMSequence 对应的页面流程、接口调用或状态转换。
export function updateDMSequence(id, data) {
  return client.put(`/dm-sequences/${id}`, data)
}

// 前端业务函数：协调 deleteDMSequence 对应的页面流程、接口调用或状态转换。
export function deleteDMSequence(id) {
  return client.delete(`/dm-sequences/${id}`)
}
