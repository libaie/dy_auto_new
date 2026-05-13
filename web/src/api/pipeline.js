import client from './client.js'

export function startPipeline(seriesId, episodeId, mode) {
  return client.post('/pipeline/start', null, { params: { series_id: seriesId, episode_id: episodeId, mode } })
}
export function resumePipeline(runId) { return client.post(`/pipeline/resume/${runId}`) }
export function listRuns(seriesId) { return client.get(`/pipeline/runs/${seriesId}`) }
export function getRun(seriesId, runId) { return client.get(`/pipeline/runs/${seriesId}/${runId}`) }
