// 前端 API 客户端：封装 auth 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：username、password 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 login 对应业务流程的处理结果。
export function login(username, password) {
  return client.post('/auth/login', { username, password })
}

// 前端业务函数：协调 registerUser 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 registerUser 对应业务流程的处理结果。
export function registerUser(data) {
  return client.post('/auth/register', data)
}

// 前端业务函数：协调 listUsers 对应的页面流程、接口调用或状态转换。
// 入参：params 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listUsers 对应业务流程的处理结果。
export function listUsers(params) {
  return client.get('/auth/users', { params })
}
