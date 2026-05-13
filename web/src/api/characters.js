import client from './client.js'

export function listCharacters() { return client.get('/characters') }
export function createCharacter(data) { return client.post('/characters', data) }
export function updateCharacter(id, data) { return client.put(`/characters/${id}`, data) }
export function deleteCharacter(id) { return client.delete(`/characters/${id}`) }
