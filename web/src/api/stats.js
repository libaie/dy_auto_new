// 前端 API 客户端：封装 stats 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function getDashboard() {
  return client.get('/stats/dashboard')
}

// 前端业务函数：协调 getDailyStats 对应的页面流程、接口调用或状态转换。
export function getDailyStats(date) {
  return client.get('/stats/daily', { params: { date } })
}

// 前端业务函数：协调 getAccountStats 对应的页面流程、接口调用或状态转换。
export function getAccountStats(accountId) {
  return client.get(`/stats/accounts/${accountId}`)
}

// 前端业务函数：协调 getRealtimeStats 对应的页面流程、接口调用或状态转换。
export function getRealtimeStats() {
  return client.get('/stats/realtime')
}
