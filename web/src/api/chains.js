// 前端 API 客户端：封装 chains 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// Templates
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listTemplates 对应业务流程的处理结果。
export function listTemplates(params = {}) {
  return client.get('/chains/templates', { params })
}

// 前端业务函数：协调 getTemplate 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getTemplate 对应业务流程的处理结果。
export function getTemplate(id) {
  return client.get(`/chains/templates/${id}`)
}

// 前端业务函数：协调 createTemplate 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createTemplate 对应业务流程的处理结果。
export function createTemplate(data) {
  return client.post('/chains/templates', data)
}

// 前端业务函数：协调 updateTemplate 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateTemplate 对应业务流程的处理结果。
export function updateTemplate(id, data) {
  return client.put(`/chains/templates/${id}`, data)
}

// 前端业务函数：协调 deleteTemplate 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteTemplate 对应业务流程的处理结果。
export function deleteTemplate(id) {
  return client.delete(`/chains/templates/${id}`)
}

// Instances
// 前端业务函数：协调 listInstances 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listInstances 对应业务流程的处理结果。
export function listInstances(params = {}) {
  return client.get('/chains/instances', { params })
}

// 前端业务函数：协调 getInstance 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getInstance 对应业务流程的处理结果。
export function getInstance(id) {
  return client.get(`/chains/instances/${id}`)
}

// 前端业务函数：协调 createInstances 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createInstances 对应业务流程的处理结果。
export function createInstances(data) {
  return client.post('/chains/instances', data)
}

// 前端业务函数：协调 cancelInstance 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 cancelInstance 对应业务流程的处理结果。
export function cancelInstance(id) {
  return client.post(`/chains/instances/${id}/cancel`)
}

// 前端业务函数：协调 retryInstance 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 retryInstance 对应业务流程的处理结果。
export function retryInstance(id) {
  return client.post(`/chains/instances/${id}/retry`)
}
