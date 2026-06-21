// 前端 API 客户端：封装 auth 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function login(username, password) {
  return client.post('/auth/login', { username, password })
}

// 前端业务函数：协调 registerUser 对应的页面流程、接口调用或状态转换。
export function registerUser(data) {
  return client.post('/auth/register', data)
}

// 前端业务函数：协调 listUsers 对应的页面流程、接口调用或状态转换。
export function listUsers(params) {
  return client.get('/auth/users', { params })
}
