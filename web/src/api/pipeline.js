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
export function listRuns(seriesId) { return client.get(`/pipeline/runs/${seriesId}`) }
export function getRun(seriesId, runId) { return client.get(`/pipeline/runs/${seriesId}/${runId}`) }
export function getRunById(runId) { return client.get(`/pipeline/runs/by-id/${runId}`) }
