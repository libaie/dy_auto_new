// 前端 API 客户端：封装 accountGroups 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listGroups(params = {}) {
  return client.get('/account-groups', { params })
}

// 前端业务函数：协调 getGroup 对应的页面流程、接口调用或状态转换。
export function getGroup(id) {
  return client.get(`/account-groups/${id}`)
}

// 前端业务函数：协调 createGroup 对应的页面流程、接口调用或状态转换。
export function createGroup(data) {
  return client.post('/account-groups', data)
}

// 前端业务函数：协调 updateGroup 对应的页面流程、接口调用或状态转换。
export function updateGroup(id, data) {
  return client.put(`/account-groups/${id}`, data)
}

// 前端业务函数：协调 deleteGroup 对应的页面流程、接口调用或状态转换。
export function deleteGroup(id) {
  return client.delete(`/account-groups/${id}`)
}

// 前端业务函数：协调 listMembers 对应的页面流程、接口调用或状态转换。
export function listMembers(groupId, params = {}) {
  return client.get(`/account-groups/${groupId}/members`, { params })
}

// 前端业务函数：协调 addMembers 对应的页面流程、接口调用或状态转换。
export function addMembers(groupId, accountIds) {
  return client.post(`/account-groups/${groupId}/members`, { account_ids: accountIds })
}

// 前端业务函数：协调 removeMembers 对应的页面流程、接口调用或状态转换。
export function removeMembers(groupId, accountIds) {
  return client.delete(`/account-groups/${groupId}/members`, { data: { account_ids: accountIds } })
}
