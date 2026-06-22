// 前端 API 客户端：封装 stats 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getDashboard 对应业务流程的处理结果。
export function getDashboard() {
  return client.get('/stats/dashboard')
}

// 前端业务函数：协调 getDailyStats 对应的页面流程、接口调用或状态转换。
// 入参：date 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getDailyStats 对应业务流程的处理结果。
export function getDailyStats(date) {
  return client.get('/stats/daily', { params: { date } })
}

// 前端业务函数：协调 getAccountStats 对应的页面流程、接口调用或状态转换。
// 入参：accountId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getAccountStats 对应业务流程的处理结果。
export function getAccountStats(accountId) {
  return client.get(`/stats/accounts/${accountId}`)
}

// 前端业务函数：协调 getRealtimeStats 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getRealtimeStats 对应业务流程的处理结果。
export function getRealtimeStats() {
  return client.get('/stats/realtime')
}
