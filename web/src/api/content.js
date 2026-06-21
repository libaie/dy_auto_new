// 前端 API 客户端：封装 content 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// --- Templates ---
export function listTemplates(params = {}) {
  return client.get('/content/templates', { params })
}

// 前端业务函数：协调 getTemplate 对应的页面流程、接口调用或状态转换。
export function getTemplate(id) {
  return client.get(`/content/templates/${id}`)
}

// 前端业务函数：协调 createTemplate 对应的页面流程、接口调用或状态转换。
export function createTemplate(data) {
  return client.post('/content/templates', data)
}

// 前端业务函数：协调 updateTemplate 对应的页面流程、接口调用或状态转换。
export function updateTemplate(id, data) {
  return client.put(`/content/templates/${id}`, data)
}

// 前端业务函数：协调 deleteTemplate 对应的页面流程、接口调用或状态转换。
export function deleteTemplate(id) {
  return client.delete(`/content/templates/${id}`)
}

// --- Sensitive Words ---
// 前端业务函数：协调 listSensitiveWords 对应的页面流程、接口调用或状态转换。
export function listSensitiveWords(params = {}) {
  return client.get('/content/sensitive-words', { params })
}

// 前端业务函数：协调 addSensitiveWord 对应的页面流程、接口调用或状态转换。
export function addSensitiveWord(word) {
  return client.post('/content/sensitive-words', { word })
}

// 前端业务函数：协调 deleteSensitiveWord 对应的页面流程、接口调用或状态转换。
export function deleteSensitiveWord(id) {
  return client.delete(`/content/sensitive-words/${id}`)
}

// --- AI Generation ---
// 前端业务函数：协调 generateContent 对应的页面流程、接口调用或状态转换。
export function generateContent(templateId, context) {
  return client.post('/content/generate', {
    template_id: templateId,
    context,
  })
}

// 前端业务函数：协调 generateKeywords 对应的页面流程、接口调用或状态转换。
export function generateKeywords(keyword, count = 10) {
  return client.post('/content/generate-keywords', { keyword, count })
}
