import client from './client.js'

export function getSettings() {
  return client.get('/settings')
}

export function updateSettings(settings) {
  return client.put('/settings', { settings })
}
