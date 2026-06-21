// 前端 API 客户端：封装 pipeline 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function startPipeline(seriesId, episodeId, mode, modelIds, directorPlan) {
  return client.post('/pipeline/start', {
    series_id: seriesId,
    episode_id: episodeId || null,
    mode: mode || 'step_by_step',
    model_ids: modelIds || null,
    director_plan: directorPlan || null,
  })
}
export function resumePipeline(runId) { return client.post(`/pipeline/resume/${runId}`) }
export function listRuns(seriesId, config) {
  return config ? client.get(`/pipeline/runs/${seriesId}`, config) : client.get(`/pipeline/runs/${seriesId}`)
}
export function getRun(seriesId, runId) { return client.get(`/pipeline/runs/${seriesId}/${runId}`) }
export function getRunById(runId) { return client.get(`/pipeline/runs/by-id/${runId}`) }
