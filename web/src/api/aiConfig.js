// 前端 API 客户端：封装 aiConfig 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// AIModel CRUD
export function listModels(params) { return client.get('/ai-models', { params }) }

export function getModelOptions(params) {
  // Backward-compatible: accept string (model_type) or object ({ model_type, scene_key })
  const query = typeof params === 'string' ? { model_type: params } : (params || {})
  return client.get('/ai-models/options', { params: query })
}

export function fetchSchema() { return client.get('/ai-models/schema') }

export function getModel(id) { return client.get(`/ai-models/${id}`) }
export function createModel(data) { return client.post('/ai-models', data) }
export function updateModel(id, data) { return client.put(`/ai-models/${id}`, data) }
export function deleteModel(id) { return client.delete(`/ai-models/${id}`) }
export function testModelConnection(id) { return client.post(`/ai-models/${id}/test`) }
