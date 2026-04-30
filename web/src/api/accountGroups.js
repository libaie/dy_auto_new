import client from './client.js'

export function listGroups(params = {}) {
  return client.get('/api/account-groups', { params })
}

export function getGroup(id) {
  return client.get(`/api/account-groups/${id}`)
}

export function createGroup(data) {
  return client.post('/api/account-groups', data)
}

export function updateGroup(id, data) {
  return client.put(`/api/account-groups/${id}`, data)
}

export function deleteGroup(id) {
  return client.delete(`/api/account-groups/${id}`)
}

export function listMembers(groupId, params = {}) {
  return client.get(`/api/account-groups/${groupId}/members`, { params })
}

export function addMembers(groupId, accountIds) {
  return client.post(`/api/account-groups/${groupId}/members`, { account_ids: accountIds })
}

export function removeMembers(groupId, accountIds) {
  return client.delete(`/api/account-groups/${groupId}/members`, { data: { account_ids: accountIds } })
}
