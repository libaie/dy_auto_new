// 前端 API 客户端：封装 agency 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAgencyExperts 对应业务流程的处理结果。
export function listAgencyExperts() {
  return client.get('/agency/experts')
}

// 前端业务函数：协调 getAgencyExpert 对应的页面流程、接口调用或状态转换。
// 入参：expertId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getAgencyExpert 对应业务流程的处理结果。
export function getAgencyExpert(expertId) {
  return client.get(`/agency/experts/${expertId}`)
}

// 前端业务函数：协调 listAgencyInvocations 对应的页面流程、接口调用或状态转换。
// 入参：params 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAgencyInvocations 对应业务流程的处理结果。
export function listAgencyInvocations(params) {
  return client.get('/agency/invocations', { params })
}

// 前端业务函数：协调 getAgencyInvocation 对应的页面流程、接口调用或状态转换。
// 入参：invocationId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getAgencyInvocation 对应业务流程的处理结果。
export function getAgencyInvocation(invocationId) {
  return client.get(`/agency/invocations/${invocationId}`)
}

// 前端业务函数：协调 listAgencyRepairTasks 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAgencyRepairTasks 对应业务流程的处理结果。
export function listAgencyRepairTasks(params = {}) {
  return client.get('/agency/repair-tasks', { params })
}

// 前端业务函数：协调 retryAgencyRepairTask 对应的页面流程、接口调用或状态转换。
// 入参：jobId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 retryAgencyRepairTask 对应业务流程的处理结果。
export function retryAgencyRepairTask(jobId) {
  return client.post(`/agency/repair-tasks/${jobId}/retry`)
}

// 前端业务函数：协调 authorizeAgencyRepairRetry 对应的页面流程、接口调用或状态转换。
// 入参：jobId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 authorizeAgencyRepairRetry 对应业务流程的处理结果。
export function authorizeAgencyRepairRetry(jobId, payload) {
  return client.post(`/agency/repair-tasks/${jobId}/authorize-retry`, payload)
}

// 前端业务函数：协调 listAgencyCreativePatches 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listAgencyCreativePatches 对应业务流程的处理结果。
export function listAgencyCreativePatches(params = {}) {
  return client.get('/agency/creative-patches', { params })
}

// 前端业务函数：协调 updateAgencyCreativePatch 对应的页面流程、接口调用或状态转换。
// 入参：patchId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateAgencyCreativePatch 对应业务流程的处理结果。
export function updateAgencyCreativePatch(patchId, payload) {
  return client.patch(`/agency/creative-patches/${patchId}`, payload)
}

// 前端业务函数：协调 approveAgencyCreativePatch 对应的页面流程、接口调用或状态转换。
// 入参：patchId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 approveAgencyCreativePatch 对应业务流程的处理结果。
export function approveAgencyCreativePatch(patchId) {
  return client.post(`/agency/creative-patches/${patchId}/approve`)
}

// 前端业务函数：协调 rejectAgencyCreativePatch 对应的页面流程、接口调用或状态转换。
// 入参：patchId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 rejectAgencyCreativePatch 对应业务流程的处理结果。
export function rejectAgencyCreativePatch(patchId, payload) {
  return client.post(`/agency/creative-patches/${patchId}/reject`, payload)
}

// 前端业务函数：协调 applyAgencyCreativePatch 对应的页面流程、接口调用或状态转换。
// 入参：patchId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 applyAgencyCreativePatch 对应业务流程的处理结果。
export function applyAgencyCreativePatch(patchId) {
  return client.post(`/agency/creative-patches/${patchId}/apply`)
}

// 前端业务函数：协调 applyApprovedAgencyCreativePatches 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 applyApprovedAgencyCreativePatches 对应业务流程的处理结果。
export function applyApprovedAgencyCreativePatches(payload) {
  return client.post('/agency/creative-patches/apply-approved', payload)
}

// 前端业务函数：协调 runAgencyAssetMultimodalReview 对应的页面流程、接口调用或状态转换。
// 入参：assetId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 runAgencyAssetMultimodalReview 对应业务流程的处理结果。
export function runAgencyAssetMultimodalReview(assetId) {
  return client.post(`/agency/assets/${assetId}/multimodal-review`)
}
