import client from './client.js'

export function login(username, password) {
  return client.post('/auth/login', { username, password })
}
