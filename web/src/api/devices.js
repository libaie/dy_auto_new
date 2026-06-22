// 前端 API 客户端：封装 devices 相关后端接口，统一给页面和组件调用。
import client from './client.js'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listDevices 对应业务流程的处理结果。
export function listDevices(params = {}) {
  return client.get('/devices', { params })
}

// 前端业务函数：协调 createDevice 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createDevice 对应业务流程的处理结果。
export function createDevice(data) {
  return client.post('/devices', data)
}

// 前端业务函数：协调 updateDevice 对应的页面流程、接口调用或状态转换。
// 入参：id、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateDevice 对应业务流程的处理结果。
export function updateDevice(id, data) {
  return client.put(`/devices/${id}`, data)
}

// 前端业务函数：协调 deleteDevice 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteDevice 对应业务流程的处理结果。
export function deleteDevice(id) {
  return client.delete(`/devices/${id}`)
}

// 前端业务函数：协调 disconnectDevice 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 disconnectDevice 对应业务流程的处理结果。
export function disconnectDevice(id) {
  return client.post(`/devices/${id}/disconnect`)
}

// --- Pairing requests ---

// 前端业务函数：协调 listPairRequests 对应的页面流程、接口调用或状态转换。
// 入参：status 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listPairRequests 对应业务流程的处理结果。
export function listPairRequests(status = 'pending') {
  return client.get('/devices/pair-requests', { params: { status } })
}

// 前端业务函数：协调 approvePairRequest 对应的页面流程、接口调用或状态转换。
// 入参：requestId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 approvePairRequest 对应业务流程的处理结果。
export function approvePairRequest(requestId) {
  return client.post(`/devices/pair-requests/${requestId}/approve`)
}

// 前端业务函数：协调 rejectPairRequest 对应的页面流程、接口调用或状态转换。
// 入参：requestId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 rejectPairRequest 对应业务流程的处理结果。
export function rejectPairRequest(requestId) {
  return client.post(`/devices/pair-requests/${requestId}/reject`)
}
