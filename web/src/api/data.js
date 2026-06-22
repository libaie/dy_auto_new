// 前端 API 客户端：封装 data 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listComments 对应业务流程的处理结果。
export function listComments(params = {}) {
  return client.get('/data/comments', { params })
}

// 前端业务函数：协调 listUsers 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listUsers 对应业务流程的处理结果。
export function listUsers(params = {}) {
  return client.get('/data/users', { params })
}

// 前端业务函数：协调 listConversations 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listConversations 对应业务流程的处理结果。
export function listConversations(params = {}) {
  return client.get('/data/conversations', { params })
}


// 前端业务函数：协调 getConversation 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getConversation 对应业务流程的处理结果。
export function getConversation(id) {
  return client.get('/data/conversations/' + encodeURIComponent(id))
}
