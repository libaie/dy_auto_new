// 前端 API 客户端：封装 data 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listComments(params = {}) {
  return client.get('/data/comments', { params })
}

export function listUsers(params = {}) {
  return client.get('/data/users', { params })
}

export function listConversations(params = {}) {
  return client.get('/data/conversations', { params })
}


export function getConversation(id) {
  return client.get('/data/conversations/' + encodeURIComponent(id))
}
