// 前端 API 客户端：封装 director 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：seriesId、episodeId、targetDuration 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 autoPlanEpisode 对应业务流程的处理结果。
export function autoPlanEpisode(seriesId, episodeId, targetDuration) {
  return client.post('/director/auto-plan', {
    series_id: seriesId,
    episode_id: episodeId,
    target_duration: targetDuration || null,
  })
}

// 前端业务函数：协调 createEpisodePlan 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createEpisodePlan 对应业务流程的处理结果。
export function createEpisodePlan(payload) {
  return client.post('/director/episode-plan', payload)
}

// 前端业务函数：协调 createShotSegments 对应的页面流程、接口调用或状态转换。
// 入参：payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createShotSegments 对应业务流程的处理结果。
export function createShotSegments(payload) {
  return client.post('/director/shot-segments', payload)
}
