// 前端 API 客户端：封装 pixelle 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 testConnection 对应业务流程的处理结果。
export function testConnection() {
  return client.get('/pixelle/test-connection')
}

// 前端业务函数：协调 getPixelleConfig 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getPixelleConfig 对应业务流程的处理结果。
export function getPixelleConfig() {
  return client.get('/pixelle/config')
}

// 前端业务函数：协调 updatePixelleConfig 对应的页面流程、接口调用或状态转换。
// 入参：updates 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updatePixelleConfig 对应业务流程的处理结果。
export function updatePixelleConfig(updates) {
  return client.put('/pixelle/config', { updates })
}
