// 前端 API 客户端：封装 chains 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// Templates
export function listTemplates(params = {}) {
  return client.get('/chains/templates', { params })
}

export function getTemplate(id) {
  return client.get(`/chains/templates/${id}`)
}

export function createTemplate(data) {
  return client.post('/chains/templates', data)
}

export function updateTemplate(id, data) {
  return client.put(`/chains/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return client.delete(`/chains/templates/${id}`)
}

// Instances
export function listInstances(params = {}) {
  return client.get('/chains/instances', { params })
}

export function getInstance(id) {
  return client.get(`/chains/instances/${id}`)
}

export function createInstances(data) {
  return client.post('/chains/instances', data)
}

export function cancelInstance(id) {
  return client.post(`/chains/instances/${id}/cancel`)
}

export function retryInstance(id) {
  return client.post(`/chains/instances/${id}/retry`)
}
