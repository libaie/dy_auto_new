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
// 前端业务函数：协调 resumePipeline 对应的页面流程、接口调用或状态转换。
export function resumePipeline(runId) { return client.post(`/pipeline/resume/${runId}`) }
// 前端业务函数：协调 listRuns 对应的页面流程、接口调用或状态转换。
export function listRuns(seriesId, config) {
  return config ? client.get(`/pipeline/runs/${seriesId}`, config) : client.get(`/pipeline/runs/${seriesId}`)
}
// 前端业务函数：协调 getRun 对应的页面流程、接口调用或状态转换。
export function getRun(seriesId, runId) { return client.get(`/pipeline/runs/${seriesId}/${runId}`) }
// 前端业务函数：协调 getRunById 对应的页面流程、接口调用或状态转换。
export function getRunById(runId) { return client.get(`/pipeline/runs/by-id/${runId}`) }
