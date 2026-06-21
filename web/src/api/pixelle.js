// 前端 API 客户端：封装 pixelle 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function testConnection() {
  return client.get('/pixelle/test-connection')
}

// 前端业务函数：协调 getPixelleConfig 对应的页面流程、接口调用或状态转换。
export function getPixelleConfig() {
  return client.get('/pixelle/config')
}

// 前端业务函数：协调 updatePixelleConfig 对应的页面流程、接口调用或状态转换。
export function updatePixelleConfig(updates) {
  return client.put('/pixelle/config', { updates })
}
