// 前端 API 客户端：封装 pipeline 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：seriesId、episodeId、mode、modelIds、directorPlan 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 startPipeline 对应业务流程的处理结果。
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
// 入参：runId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 resumePipeline 对应业务流程的处理结果。
export function resumePipeline(runId) { return client.post(`/pipeline/resume/${runId}`) }
// 前端业务函数：协调 listRuns 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、config 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listRuns 对应业务流程的处理结果。
export function listRuns(seriesId, config) {
  return config ? client.get(`/pipeline/runs/${seriesId}`, config) : client.get(`/pipeline/runs/${seriesId}`)
}
// 前端业务函数：协调 getRun 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、runId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getRun 对应业务流程的处理结果。
export function getRun(seriesId, runId) { return client.get(`/pipeline/runs/${seriesId}/${runId}`) }
// 前端业务函数：协调 getRunById 对应的页面流程、接口调用或状态转换。
// 入参：runId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getRunById 对应业务流程的处理结果。
export function getRunById(runId) { return client.get(`/pipeline/runs/by-id/${runId}`) }
