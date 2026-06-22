// 前端 API 客户端：封装 dmSequences 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listDMSequences 对应业务流程的处理结果。
export function listDMSequences(params = {}) {
  return client.get('/dm-sequences', params)
}

// 前端业务函数：协调 getDMSequence 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getDMSequence 对应业务流程的处理结果。
export function getDMSequence(id) {
  return client.get(`/dm-sequences/${id}`)
}

// 前端业务函数：协调 createDMSequence 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createDMSequence 对应业务流程的处理结果。
export function createDMSequence(data) {
  return client.post('/dm-sequences', data)
}

// 前端业务函数：协调 updateDMSequence 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateDMSequence 对应业务流程的处理结果。
export function updateDMSequence(id, data) {
  return client.put(`/dm-sequences/${id}`, data)
}

// 前端业务函数：协调 deleteDMSequence 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteDMSequence 对应业务流程的处理结果。
export function deleteDMSequence(id) {
  return client.delete(`/dm-sequences/${id}`)
}
