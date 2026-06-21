// 前端 API 客户端：封装 scenes 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listScenes(params) { return client.get('/scenes', { params }) }
export function createScene(data) { return client.post('/scenes', data) }
export function updateScene(id, data) { return client.put(`/scenes/${id}`, data) }
// 前端业务函数：协调 deleteScene 对应的页面流程、接口调用或状态转换。
export function deleteScene(id) { return client.delete(`/scenes/${id}`) }
// 前端业务函数：协调 autoGenerateScenes 对应的页面流程、接口调用或状态转换。
export function autoGenerateScenes(text, genre = 'drama', count = 5) { return client.post('/scenes/auto-generate', { text, genre, count }) }
// 前端业务函数：协调 aiRewriteScene 对应的页面流程、接口调用或状态转换。
export function aiRewriteScene(id, data = {}) { return client.post(`/scenes/${id}/ai-rewrite-candidate`, data) }
// 前端业务函数：协调 generateSceneReferences 对应的页面流程、接口调用或状态转换。
export function generateSceneReferences(id, data = {}) { return client.post(`/scenes/${id}/reference-images/generate`, data) }
