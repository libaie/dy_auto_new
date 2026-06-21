// 前端 API 客户端：封装 characters 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listCharacters(params) { return client.get('/characters', { params }) }
export function createCharacter(data) { return client.post('/characters', data) }
export function updateCharacter(id, data) { return client.put(`/characters/${id}`, data) }
// 前端业务函数：协调 deleteCharacter 对应的页面流程、接口调用或状态转换。
export function deleteCharacter(id) { return client.delete(`/characters/${id}`) }
// 前端业务函数：协调 autoGenerateCharacters 对应的页面流程、接口调用或状态转换。
export function autoGenerateCharacters(text, genre = 'drama', count = 4) { return client.post('/characters/auto-generate', { text, genre, count }) }
// 前端业务函数：协调 aiRewriteCharacter 对应的页面流程、接口调用或状态转换。
export function aiRewriteCharacter(id, data = {}) { return client.post(`/characters/${id}/ai-rewrite-candidate`, data) }
// 前端业务函数：协调 generateCharacterReferences 对应的页面流程、接口调用或状态转换。
export function generateCharacterReferences(id, data = {}) { return client.post(`/characters/${id}/reference-images/generate`, data) }
