import client from './client.js'

export function listSeries(params) { return client.get('/series', { params }) }
export function createSeries(data) { return client.post('/series', data) }
export function getSeries(id) { return client.get(`/series/${id}`) }
export function deleteSeries(id) { return client.delete(`/series/${id}`) }
export function linkCharacter(seriesId, characterId) { return client.post(`/series/${seriesId}/characters/${characterId}`) }
export function linkScene(seriesId, sceneId) { return client.post(`/series/${seriesId}/scenes/${sceneId}`) }
export function updateEpisode(seriesId, episodeId, data) { return client.put(`/series/${seriesId}/episodes/${episodeId}`, data) }
export function autoGenerateAssets(seriesId) { return client.post(`/series/${seriesId}/auto-generate`) }
