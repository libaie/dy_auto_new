import client from './client.js'

const STYLE_LOCK_TIMEOUT_MS = 600000

export function listSeries(params) { return client.get('/series', { params }) }
export function createSeries(data) { return client.post('/series', data) }
export function getSeries(id) { return client.get(`/series/${id}`) }
export function updateSeries(id, data) { return client.put(`/series/${id}`, data) }
export function deleteSeries(id) { return client.delete(`/series/${id}`) }
export function linkCharacter(seriesId, characterId) { return client.post(`/series/${seriesId}/characters/${characterId}`) }
export function unlinkCharacter(seriesId, characterId) { return client.delete(`/series/${seriesId}/characters/${characterId}`) }
export function linkScene(seriesId, sceneId) { return client.post(`/series/${seriesId}/scenes/${sceneId}`) }
export function unlinkScene(seriesId, sceneId) { return client.delete(`/series/${seriesId}/scenes/${sceneId}`) }
export function updateEpisode(seriesId, episodeId, data) { return client.put(`/series/${seriesId}/episodes/${episodeId}`, data) }
export function autoGenerateAssets(seriesId) { return client.post(`/series/${seriesId}/auto-generate`) }
export function getStyleLock(seriesId) { return client.get(`/series/${seriesId}/style-lock`) }
export function lockSeriesStyle(seriesId) { return client.post(`/series/${seriesId}/style-lock`, undefined, { timeout: STYLE_LOCK_TIMEOUT_MS }) }
export function getAgencyConsole(seriesId) { return client.get(`/series/${seriesId}/agency-console`) }
