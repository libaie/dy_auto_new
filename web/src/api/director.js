// 前端 API 客户端：封装 director 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function autoPlanEpisode(seriesId, episodeId, targetDuration) {
  return client.post('/director/auto-plan', {
    series_id: seriesId,
    episode_id: episodeId,
    target_duration: targetDuration || null,
  })
}

export function createEpisodePlan(payload) {
  return client.post('/director/episode-plan', payload)
}

export function createShotSegments(payload) {
  return client.post('/director/shot-segments', payload)
}
