// 前端 API 客户端：封装 accountGroups 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listGroups(params = {}) {
  return client.get('/account-groups', { params })
}

export function getGroup(id) {
  return client.get(`/account-groups/${id}`)
}

export function createGroup(data) {
  return client.post('/account-groups', data)
}

export function updateGroup(id, data) {
  return client.put(`/account-groups/${id}`, data)
}

export function deleteGroup(id) {
  return client.delete(`/account-groups/${id}`)
}

export function listMembers(groupId, params = {}) {
  return client.get(`/account-groups/${groupId}/members`, { params })
}

export function addMembers(groupId, accountIds) {
  return client.post(`/account-groups/${groupId}/members`, { account_ids: accountIds })
}

export function removeMembers(groupId, accountIds) {
  return client.delete(`/account-groups/${groupId}/members`, { data: { account_ids: accountIds } })
}
