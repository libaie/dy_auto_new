// 前端 API 客户端：封装 auth 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function login(username, password) {
  return client.post('/auth/login', { username, password })
}

export function registerUser(data) {
  return client.post('/auth/register', data)
}

export function listUsers(params) {
  return client.get('/auth/users', { params })
}
