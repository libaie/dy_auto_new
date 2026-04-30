import client from './client.js'

export function listAccounts(params = {}) {
  return client.get('/accounts', { params })
}

export function createAccount(data) {
  return client.post('/accounts', data)
}

export function updateAccount(id, data) {
  return client.put(`/accounts/${id}`, data)
}

export function deleteAccount(id) {
  return client.delete(`/accounts/${id}`)
}
