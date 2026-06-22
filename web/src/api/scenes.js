// 前端 API 客户端：封装 scenes 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：params 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listScenes 对应业务流程的处理结果。
export function listScenes(params) { return client.get('/scenes', { params }) }
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createScene 对应业务流程的处理结果。
export function createScene(data) { return client.post('/scenes', data) }
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateScene 对应业务流程的处理结果。
export function updateScene(id, data) { return client.put(`/scenes/${id}`, data) }
// 前端业务函数：协调 deleteScene 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteScene 对应业务流程的处理结果。
export function deleteScene(id) { return client.delete(`/scenes/${id}`) }
// 前端业务函数：协调 autoGenerateScenes 对应的页面流程、接口调用或状态转换。
// 入参：text、genre、count 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 autoGenerateScenes 对应业务流程的处理结果。
export function autoGenerateScenes(text, genre = 'drama', count = 5) { return client.post('/scenes/auto-generate', { text, genre, count }) }
// 前端业务函数：协调 aiRewriteScene 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 aiRewriteScene 对应业务流程的处理结果。
export function aiRewriteScene(id, data = {}) { return client.post(`/scenes/${id}/ai-rewrite-candidate`, data) }
// 前端业务函数：协调 generateSceneReferences 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateSceneReferences 对应业务流程的处理结果。
export function generateSceneReferences(id, data = {}) { return client.post(`/scenes/${id}/reference-images/generate`, data) }
