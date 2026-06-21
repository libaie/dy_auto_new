// 前端 API 客户端：封装 scenes 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listScenes(params) { return client.get('/scenes', { params }) }
export function createScene(data) { return client.post('/scenes', data) }
export function updateScene(id, data) { return client.put(`/scenes/${id}`, data) }
export function deleteScene(id) { return client.delete(`/scenes/${id}`) }
export function autoGenerateScenes(text, genre = 'drama', count = 5) { return client.post('/scenes/auto-generate', { text, genre, count }) }
export function aiRewriteScene(id, data = {}) { return client.post(`/scenes/${id}/ai-rewrite-candidate`, data) }
export function generateSceneReferences(id, data = {}) { return client.post(`/scenes/${id}/reference-images/generate`, data) }
