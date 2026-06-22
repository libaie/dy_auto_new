// 前端 API 客户端：封装 accountGroups 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listGroups 对应业务流程的处理结果。
export function listGroups(params = {}) {
  return client.get('/account-groups', { params })
}

// 前端业务函数：协调 getGroup 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getGroup 对应业务流程的处理结果。
export function getGroup(id) {
  return client.get(`/account-groups/${id}`)
}

// 前端业务函数：协调 createGroup 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createGroup 对应业务流程的处理结果。
export function createGroup(data) {
  return client.post('/account-groups', data)
}

// 前端业务函数：协调 updateGroup 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateGroup 对应业务流程的处理结果。
export function updateGroup(id, data) {
  return client.put(`/account-groups/${id}`, data)
}

// 前端业务函数：协调 deleteGroup 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteGroup 对应业务流程的处理结果。
export function deleteGroup(id) {
  return client.delete(`/account-groups/${id}`)
}

// 前端业务函数：协调 listMembers 对应的页面流程、接口调用或状态转换。
// 入参：groupId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listMembers 对应业务流程的处理结果。
export function listMembers(groupId, params = {}) {
  return client.get(`/account-groups/${groupId}/members`, { params })
}

// 前端业务函数：协调 addMembers 对应的页面流程、接口调用或状态转换。
// 入参：groupId、accountIds 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 addMembers 对应业务流程的处理结果。
export function addMembers(groupId, accountIds) {
  return client.post(`/account-groups/${groupId}/members`, { account_ids: accountIds })
}

// 前端业务函数：协调 removeMembers 对应的页面流程、接口调用或状态转换。
// 入参：groupId、accountIds 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 removeMembers 对应业务流程的处理结果。
export function removeMembers(groupId, accountIds) {
  return client.delete(`/account-groups/${groupId}/members`, { data: { account_ids: accountIds } })
}
