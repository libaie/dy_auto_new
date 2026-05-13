import client from './client.js'

export function getModels() { return client.get('/ai-config/models') }
export function updateModels(data) { return client.put('/ai-config/models', data) }
