// 前端 API 客户端：封装 aiTextArtifacts 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAITextArtifacts 对应业务流程的处理结果。
export function listAITextArtifacts(params = {}, config = {}) {
  return client.get('/ai-text-artifacts', { params, ...config })
}

// 前端业务函数：协调 getAITextArtifact 对应的页面流程、接口调用或状态转换。
// 入参：artifactId、config 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getAITextArtifact 对应业务流程的处理结果。
export function getAITextArtifact(artifactId, config) {
  return config ? client.get(`/ai-text-artifacts/${artifactId}`, config) : client.get(`/ai-text-artifacts/${artifactId}`)
}

// 前端业务函数：协调 getAITextArtifactLineage 对应的页面流程、接口调用或状态转换。
// 入参：artifactId、config 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getAITextArtifactLineage 对应业务流程的处理结果。
export function getAITextArtifactLineage(artifactId, config) {
  return config ? client.get(`/ai-text-artifacts/${artifactId}/lineage`, config) : client.get(`/ai-text-artifacts/${artifactId}/lineage`)
}

// 前端业务函数：协调 editAITextArtifact 对应的页面流程、接口调用或状态转换。
// 入参：artifactId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 editAITextArtifact 对应业务流程的处理结果。
export function editAITextArtifact(artifactId, payload) {
  return client.post(`/ai-text-artifacts/${artifactId}/edit`, payload)
}

// 前端业务函数：协调 approveAITextArtifact 对应的页面流程、接口调用或状态转换。
// 入参：artifactId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 approveAITextArtifact 对应业务流程的处理结果。
export function approveAITextArtifact(artifactId) {
  return client.post(`/ai-text-artifacts/${artifactId}/approve`)
}

// 前端业务函数：协调 regenerateAITextArtifact 对应的页面流程、接口调用或状态转换。
// 入参：artifactId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 regenerateAITextArtifact 对应业务流程的处理结果。
export function regenerateAITextArtifact(artifactId, payload) {
  return client.post(`/ai-text-artifacts/${artifactId}/regenerate`, payload)
}
