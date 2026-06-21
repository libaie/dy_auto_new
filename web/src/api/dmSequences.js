// 前端 API 客户端：封装 dmSequences 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listDMSequences(params = {}) {
  return client.get('/dm-sequences', params)
}

export function getDMSequence(id) {
  return client.get(`/dm-sequences/${id}`)
}

export function createDMSequence(data) {
  return client.post('/dm-sequences', data)
}

export function updateDMSequence(id, data) {
  return client.put(`/dm-sequences/${id}`, data)
}

export function deleteDMSequence(id) {
  return client.delete(`/dm-sequences/${id}`)
}
