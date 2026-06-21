// 前端 API 客户端：封装 data 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listComments(params = {}) {
  return client.get('/data/comments', { params })
}

// 前端业务函数：协调 listUsers 对应的页面流程、接口调用或状态转换。
export function listUsers(params = {}) {
  return client.get('/data/users', { params })
}

// 前端业务函数：协调 listConversations 对应的页面流程、接口调用或状态转换。
export function listConversations(params = {}) {
  return client.get('/data/conversations', { params })
}


// 前端业务函数：协调 getConversation 对应的页面流程、接口调用或状态转换。
export function getConversation(id) {
  return client.get('/data/conversations/' + encodeURIComponent(id))
}
