import client from './client.js'

export function listCharacters(params) { return client.get('/characters', { params }) }
export function createCharacter(data) { return client.post('/characters', data) }
export function updateCharacter(id, data) { return client.put(`/characters/${id}`, data) }
export function deleteCharacter(id) { return client.delete(`/characters/${id}`) }
export function autoGenerateCharacters(text, genre = 'drama', count = 4) { return client.post('/characters/auto-generate', { text, genre, count }) }
export function aiRewriteCharacter(id, data = {}) { return client.post(`/characters/${id}/ai-rewrite-candidate`, data) }
export function generateCharacterReferences(id, data = {}) { return client.post(`/characters/${id}/reference-images/generate`, data) }
