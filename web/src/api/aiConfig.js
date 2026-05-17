import client from './client.js'

// AIModel CRUD
export function listModels(params) { return client.get('/ai-models', { params }) }
export function getModelOptions(modelType) { return client.get('/ai-models/options', { params: { model_type: modelType } }) }
export function getModel(id) { return client.get(`/ai-models/${id}`) }
export function createModel(data) { return client.post('/ai-models', data) }
export function updateModel(id, data) { return client.put(`/ai-models/${id}`, data) }
export function deleteModel(id) { return client.delete(`/ai-models/${id}`) }
export function testModelConnection(id) { return client.post(`/ai-models/${id}/test`) }
