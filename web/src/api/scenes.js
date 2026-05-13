import client from './client.js'

export function listScenes() { return client.get('/scenes') }
export function createScene(data) { return client.post('/scenes', data) }
export function updateScene(id, data) { return client.put(`/scenes/${id}`, data) }
export function deleteScene(id) { return client.delete(`/scenes/${id}`) }
export function autoGenerateScenes(text, genre = 'drama', count = 5) { return client.post('/scenes/auto-generate', { text, genre, count }) }
