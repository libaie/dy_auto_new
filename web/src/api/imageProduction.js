// 前端 API 客户端：封装 imageProduction 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listImageProductionStrategies 对应业务流程的处理结果。
export function listImageProductionStrategies(params = {}) {
  return client.get('/image-production/strategies', { params })
}

// 前端业务函数：协调 createImageProductionStrategy 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createImageProductionStrategy 对应业务流程的处理结果。
export function createImageProductionStrategy(payload) {
  return client.post('/image-production/strategies', payload)
}

// 前端业务函数：协调 updateImageProductionStrategy 对应的页面流程、接口调用或状态转换。
// 入参：strategyId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateImageProductionStrategy 对应业务流程的处理结果。
export function updateImageProductionStrategy(strategyId, payload) {
  return client.put(`/image-production/strategies/${strategyId}`, payload)
}

// 前端业务函数：协调 archiveImageProductionStrategy 对应的页面流程、接口调用或状态转换。
// 入参：strategyId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 archiveImageProductionStrategy 对应业务流程的处理结果。
export function archiveImageProductionStrategy(strategyId) {
  return client.post(`/image-production/strategies/${strategyId}/archive`)
}

// 前端业务函数：协调 activateImageProductionStrategy 对应的页面流程、接口调用或状态转换。
// 入参：strategyId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 activateImageProductionStrategy 对应业务流程的处理结果。
export function activateImageProductionStrategy(strategyId) {
  return client.post(`/image-production/strategies/${strategyId}/activate`)
}

// 前端业务函数：协调 refreshImageProductionMetrics 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 refreshImageProductionMetrics 对应业务流程的处理结果。
export function refreshImageProductionMetrics(payload = {}) {
  return client.post('/image-production/strategies/metrics/refresh', payload)
}

// 前端业务函数：协调 getImageProductionStrategyRecommendations 对应的页面流程、接口调用或状态转换。
// 入参：strategyId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getImageProductionStrategyRecommendations 对应业务流程的处理结果。
export function getImageProductionStrategyRecommendations(strategyId) {
  return client.get(`/image-production/strategies/${strategyId}/recommendations`)
}

// 前端业务函数：协调 previewImageSelection 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 previewImageSelection 对应业务流程的处理结果。
export function previewImageSelection(payload) {
  return client.post('/image-production/selection-preview', payload)
}

// 前端业务函数：协调 promoteImageAssetToVideo 对应的页面流程、接口调用或状态转换。
// 入参：assetId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 promoteImageAssetToVideo 对应业务流程的处理结果。
export function promoteImageAssetToVideo(assetId, payload) {
  return client.post(`/image-production/assets/${assetId}/promote-to-video-asset`, payload)
}

// 前端业务函数：协调 previewImageAbTest 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 previewImageAbTest 对应业务流程的处理结果。
export function previewImageAbTest(payload) {
  return client.post('/image-production/ab-tests/preview', payload)
}

// 前端业务函数：协调 createImageAbTest 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createImageAbTest 对应业务流程的处理结果。
export function createImageAbTest(payload) {
  return client.post('/image-production/ab-tests', payload)
}

// 前端业务函数：协调 getImageAbTest 对应的页面流程、接口调用或状态转换。
// 入参：groupId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getImageAbTest 对应业务流程的处理结果。
export function getImageAbTest(groupId) {
  return client.get(`/image-production/ab-tests/${groupId}`)
}

// 前端业务函数：协调 refreshImageAbTest 对应的页面流程、接口调用或状态转换。
// 入参：groupId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 refreshImageAbTest 对应业务流程的处理结果。
export function refreshImageAbTest(groupId) {
  return client.post(`/image-production/ab-tests/${groupId}/refresh`)
}

// 前端业务函数：协调 getImageAbWinnerRecommendation 对应的页面流程、接口调用或状态转换。
// 入参：groupId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getImageAbWinnerRecommendation 对应业务流程的处理结果。
export function getImageAbWinnerRecommendation(groupId) {
  return client.get(`/image-production/ab-tests/${groupId}/winner-recommendation`)
}

// 前端业务函数：协调 chooseImageAbWinner 对应的页面流程、接口调用或状态转换。
// 入参：groupId、attemptId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 chooseImageAbWinner 对应业务流程的处理结果。
export function chooseImageAbWinner(groupId, attemptId, payload) {
  return client.post(`/image-production/ab-tests/${groupId}/winner/${attemptId}`, payload)
}

// 前端业务函数：协调 chooseImageAbNoWinner 对应的页面流程、接口调用或状态转换。
// 入参：groupId、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 chooseImageAbNoWinner 对应业务流程的处理结果。
export function chooseImageAbNoWinner(groupId, payload) {
  return client.post(`/image-production/ab-tests/${groupId}/no-winner`, payload)
}
