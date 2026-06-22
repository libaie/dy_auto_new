// 前端 API 客户端：封装 aiConfig 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// AIModel CRUD
// 入参：params 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listModels 对应业务流程的处理结果。
export function listModels(params) { return client.get('/ai-models', { params }) }

// 前端业务函数：协调 getModelOptions 对应的页面流程、接口调用或状态转换。
// 入参：params 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getModelOptions 对应业务流程的处理结果。
export function getModelOptions(params) {
  // Backward-compatible: accept string (model_type) or object ({ model_type, scene_key })
  const query = typeof params === 'string' ? { model_type: params } : (params || {})
  return client.get('/ai-models/options', { params: query })
}

// 前端业务函数：协调 fetchSchema 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 fetchSchema 对应业务流程的处理结果。
export function fetchSchema() { return client.get('/ai-models/schema') }

// 前端业务函数：协调 getModel 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getModel 对应业务流程的处理结果。
export function getModel(id) { return client.get(`/ai-models/${id}`) }
// 前端业务函数：协调 createModel 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createModel 对应业务流程的处理结果。
export function createModel(data) { return client.post('/ai-models', data) }
// 前端业务函数：协调 updateModel 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateModel 对应业务流程的处理结果。
export function updateModel(id, data) { return client.put(`/ai-models/${id}`, data) }
// 前端业务函数：协调 deleteModel 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteModel 对应业务流程的处理结果。
export function deleteModel(id) { return client.delete(`/ai-models/${id}`) }
// 前端业务函数：协调 testModelConnection 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 testModelConnection 对应业务流程的处理结果。
export function testModelConnection(id) { return client.post(`/ai-models/${id}/test`) }
