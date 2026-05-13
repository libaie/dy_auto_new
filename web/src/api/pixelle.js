import client from './client.js'

export function testConnection() {
  return client.get('/pixelle/test-connection')
}

export function getPixelleConfig() {
  return client.get('/pixelle/config')
}

export function updatePixelleConfig(updates) {
  return client.put('/pixelle/config', { updates })
}
