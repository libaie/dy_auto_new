// 前端 API 客户端：封装 aiConfig 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// AIModel CRUD
export function listModels(params) { return client.get('/ai-models', { params }) }

// 前端业务函数：协调 getModelOptions 对应的页面流程、接口调用或状态转换。
export function getModelOptions(params) {
  // Backward-compatible: accept string (model_type) or object ({ model_type, scene_key })
  const query = typeof params === 'string' ? { model_type: params } : (params || {})
  return client.get('/ai-models/options', { params: query })
}

// 前端业务函数：协调 fetchSchema 对应的页面流程、接口调用或状态转换。
export function fetchSchema() { return client.get('/ai-models/schema') }

// 前端业务函数：协调 getModel 对应的页面流程、接口调用或状态转换。
export function getModel(id) { return client.get(`/ai-models/${id}`) }
// 前端业务函数：协调 createModel 对应的页面流程、接口调用或状态转换。
export function createModel(data) { return client.post('/ai-models', data) }
// 前端业务函数：协调 updateModel 对应的页面流程、接口调用或状态转换。
export function updateModel(id, data) { return client.put(`/ai-models/${id}`, data) }
// 前端业务函数：协调 deleteModel 对应的页面流程、接口调用或状态转换。
export function deleteModel(id) { return client.delete(`/ai-models/${id}`) }
// 前端业务函数：协调 testModelConnection 对应的页面流程、接口调用或状态转换。
export function testModelConnection(id) { return client.post(`/ai-models/${id}/test`) }
