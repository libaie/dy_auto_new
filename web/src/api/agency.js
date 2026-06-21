// 前端 API 客户端：封装 agency 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listAgencyExperts() {
  return client.get('/agency/experts')
}

export function getAgencyExpert(expertId) {
  return client.get(`/agency/experts/${expertId}`)
}

export function listAgencyInvocations(params) {
  return client.get('/agency/invocations', { params })
}

export function getAgencyInvocation(invocationId) {
  return client.get(`/agency/invocations/${invocationId}`)
}

export function listAgencyRepairTasks(params = {}) {
  return client.get('/agency/repair-tasks', { params })
}

export function retryAgencyRepairTask(jobId) {
  return client.post(`/agency/repair-tasks/${jobId}/retry`)
}

export function authorizeAgencyRepairRetry(jobId, payload) {
  return client.post(`/agency/repair-tasks/${jobId}/authorize-retry`, payload)
}

export function listAgencyCreativePatches(params = {}) {
  return client.get('/agency/creative-patches', { params })
}

export function updateAgencyCreativePatch(patchId, payload) {
  return client.patch(`/agency/creative-patches/${patchId}`, payload)
}

export function approveAgencyCreativePatch(patchId) {
  return client.post(`/agency/creative-patches/${patchId}/approve`)
}

export function rejectAgencyCreativePatch(patchId, payload) {
  return client.post(`/agency/creative-patches/${patchId}/reject`, payload)
}

export function applyAgencyCreativePatch(patchId) {
  return client.post(`/agency/creative-patches/${patchId}/apply`)
}

export function applyApprovedAgencyCreativePatches(payload) {
  return client.post('/agency/creative-patches/apply-approved', payload)
}

export function runAgencyAssetMultimodalReview(assetId) {
  return client.post(`/agency/assets/${assetId}/multimodal-review`)
}
