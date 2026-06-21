// 前端 API 客户端：封装 aiTextArtifacts 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listAITextArtifacts(params = {}, config = {}) {
  return client.get('/ai-text-artifacts', { params, ...config })
}

// 前端业务函数：协调 getAITextArtifact 对应的页面流程、接口调用或状态转换。
export function getAITextArtifact(artifactId, config) {
  return config ? client.get(`/ai-text-artifacts/${artifactId}`, config) : client.get(`/ai-text-artifacts/${artifactId}`)
}

// 前端业务函数：协调 getAITextArtifactLineage 对应的页面流程、接口调用或状态转换。
export function getAITextArtifactLineage(artifactId, config) {
  return config ? client.get(`/ai-text-artifacts/${artifactId}/lineage`, config) : client.get(`/ai-text-artifacts/${artifactId}/lineage`)
}

// 前端业务函数：协调 editAITextArtifact 对应的页面流程、接口调用或状态转换。
export function editAITextArtifact(artifactId, payload) {
  return client.post(`/ai-text-artifacts/${artifactId}/edit`, payload)
}

// 前端业务函数：协调 approveAITextArtifact 对应的页面流程、接口调用或状态转换。
export function approveAITextArtifact(artifactId) {
  return client.post(`/ai-text-artifacts/${artifactId}/approve`)
}

// 前端业务函数：协调 regenerateAITextArtifact 对应的页面流程、接口调用或状态转换。
export function regenerateAITextArtifact(artifactId, payload) {
  return client.post(`/ai-text-artifacts/${artifactId}/regenerate`, payload)
}
