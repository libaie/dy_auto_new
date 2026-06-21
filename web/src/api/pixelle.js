// 前端 API 客户端：封装 pixelle 相关后端接口，统一给页面和组件调用。
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
