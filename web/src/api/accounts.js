// 前端 API 客户端：封装 accounts 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAccounts 对应业务流程的处理结果。
export function listAccounts(params = {}) {
  return client.get('/accounts', { params })
}

// 前端业务函数：协调 createAccount 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createAccount 对应业务流程的处理结果。
export function createAccount(data) {
  return client.post('/accounts', data)
}

// 前端业务函数：协调 updateAccount 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateAccount 对应业务流程的处理结果。
export function updateAccount(id, data) {
  return client.put(`/accounts/${id}`, data)
}

// 前端业务函数：协调 deleteAccount 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteAccount 对应业务流程的处理结果。
export function deleteAccount(id) {
  return client.delete(`/accounts/${id}`)
}
