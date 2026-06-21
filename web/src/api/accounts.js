// 前端 API 客户端：封装 accounts 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listAccounts(params = {}) {
  return client.get('/accounts', { params })
}

// 前端业务函数：协调 createAccount 对应的页面流程、接口调用或状态转换。
export function createAccount(data) {
  return client.post('/accounts', data)
}

// 前端业务函数：协调 updateAccount 对应的页面流程、接口调用或状态转换。
export function updateAccount(id, data) {
  return client.put(`/accounts/${id}`, data)
}

// 前端业务函数：协调 deleteAccount 对应的页面流程、接口调用或状态转换。
export function deleteAccount(id) {
  return client.delete(`/accounts/${id}`)
}
