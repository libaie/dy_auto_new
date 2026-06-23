// 前端 API 客户端：封装 series 相关后端接口，统一给页面和组件调用。
import client from './client.js'

const STYLE_LOCK_TIMEOUT_MS = 600000
const AUTO_GENERATE_ASSETS_TIMEOUT_MS = 600000
const EPISODE_SCRIPT_TIMEOUT_MS = 600000

// 前端业务函数：协调 listSeries 对应的页面流程、接口调用或状态转换。
// 入参：params 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listSeries 对应业务流程的处理结果。
export function listSeries(params) { return client.get('/series', { params }) }
// 前端业务函数：协调 createSeries 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createSeries 对应业务流程的处理结果。
export function createSeries(data) { return client.post('/series', data) }
// 前端业务函数：协调 getSeries 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getSeries 对应业务流程的处理结果。
export function getSeries(id) { return client.get(`/series/${id}`) }
// 前端业务函数：协调 ensureSeriesEpisodes 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 ensureSeriesEpisodes 对应业务流程的处理结果。
export function ensureSeriesEpisodes(id) { return client.post(`/series/${id}/ensure-episodes`) }
// 前端业务函数：协调 generateSeriesStoryPlan 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateSeriesStoryPlan 对应业务流程的处理结果。
export function generateSeriesStoryPlan(id, options = {}) {
  if (options.force) return client.post(`/series/${id}/story-plan`, undefined, { params: { force: true } })
  return client.post(`/series/${id}/story-plan`)
}
// 前端业务函数：协调 generateEpisodeScript 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、episodeId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateEpisodeScript 对应业务流程的处理结果。
export function generateEpisodeScript(seriesId, episodeId, data = {}) { return client.post(`/series/${seriesId}/episodes/${episodeId}/script`, data, { timeout: EPISODE_SCRIPT_TIMEOUT_MS }) }
// 前端业务函数：协调 updateSeries 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateSeries 对应业务流程的处理结果。
export function updateSeries(id, data) { return client.put(`/series/${id}`, data) }
// 前端业务函数：协调 deleteSeries 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteSeries 对应业务流程的处理结果。
export function deleteSeries(id) { return client.delete(`/series/${id}`) }
// 前端业务函数：协调 linkCharacter 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、characterId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 linkCharacter 对应业务流程的处理结果。
export function linkCharacter(seriesId, characterId) { return client.post(`/series/${seriesId}/characters/${characterId}`) }
// 前端业务函数：协调 unlinkCharacter 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、characterId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 unlinkCharacter 对应业务流程的处理结果。
export function unlinkCharacter(seriesId, characterId) { return client.delete(`/series/${seriesId}/characters/${characterId}`) }
// 前端业务函数：协调 linkScene 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、sceneId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 linkScene 对应业务流程的处理结果。
export function linkScene(seriesId, sceneId) { return client.post(`/series/${seriesId}/scenes/${sceneId}`) }
// 前端业务函数：协调 unlinkScene 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、sceneId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 unlinkScene 对应业务流程的处理结果。
export function unlinkScene(seriesId, sceneId) { return client.delete(`/series/${seriesId}/scenes/${sceneId}`) }
// 前端业务函数：协调 updateEpisode 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、episodeId、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateEpisode 对应业务流程的处理结果。
export function updateEpisode(seriesId, episodeId, data) { return client.put(`/series/${seriesId}/episodes/${episodeId}`, data) }
// 前端业务函数：协调 autoGenerateAssets 对应的页面流程、接口调用或状态转换。
// 入参：seriesId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 autoGenerateAssets 对应业务流程的处理结果。
export function autoGenerateAssets(seriesId) { return client.post(`/series/${seriesId}/auto-generate`, undefined, { timeout: AUTO_GENERATE_ASSETS_TIMEOUT_MS }) }
// 前端业务函数：协调 getStyleLock 对应的页面流程、接口调用或状态转换。
// 入参：seriesId、config 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getStyleLock 对应业务流程的处理结果。
export function getStyleLock(seriesId, config) {
  return config ? client.get(`/series/${seriesId}/style-lock`, config) : client.get(`/series/${seriesId}/style-lock`)
}
// 前端业务函数：协调 lockSeriesStyle 对应的页面流程、接口调用或状态转换。
// 入参：seriesId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 lockSeriesStyle 对应业务流程的处理结果。
export function lockSeriesStyle(seriesId) { return client.post(`/series/${seriesId}/style-lock`, undefined, { timeout: STYLE_LOCK_TIMEOUT_MS }) }
// 前端业务函数：协调 getAgencyConsole 对应的页面流程、接口调用或状态转换。
// 入参：seriesId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getAgencyConsole 对应业务流程的处理结果。
export function getAgencyConsole(seriesId) { return client.get(`/series/${seriesId}/agency-console`) }
