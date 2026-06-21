// 前端 API 客户端：封装 settings 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function getSettings() {
  return client.get('/settings')
}

export function updateSettings(settings) {
  return client.put('/settings', { settings })
}
