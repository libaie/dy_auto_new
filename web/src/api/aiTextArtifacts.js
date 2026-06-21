// 前端 API 客户端：封装 aiTextArtifacts 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listAITextArtifacts(params = {}, config = {}) {
  return client.get('/ai-text-artifacts', { params, ...config })
}

export function getAITextArtifact(artifactId, config) {
  return config ? client.get(`/ai-text-artifacts/${artifactId}`, config) : client.get(`/ai-text-artifacts/${artifactId}`)
}

export function getAITextArtifactLineage(artifactId, config) {
  return config ? client.get(`/ai-text-artifacts/${artifactId}/lineage`, config) : client.get(`/ai-text-artifacts/${artifactId}/lineage`)
}

export function editAITextArtifact(artifactId, payload) {
  return client.post(`/ai-text-artifacts/${artifactId}/edit`, payload)
}

export function approveAITextArtifact(artifactId) {
  return client.post(`/ai-text-artifacts/${artifactId}/approve`)
}

export function regenerateAITextArtifact(artifactId, payload) {
  return client.post(`/ai-text-artifacts/${artifactId}/regenerate`, payload)
}
