// 前端 API 客户端：封装 devices 相关后端接口，统一给页面和组件调用。
import client from './client.js'

export function listDevices(params = {}) {
  return client.get('/devices', { params })
}

export function createDevice(data) {
  return client.post('/devices', data)
}

export function updateDevice(id, data) {
  return client.put(`/devices/${id}`, data)
}

export function deleteDevice(id) {
  return client.delete(`/devices/${id}`)
}

export function disconnectDevice(id) {
  return client.post(`/devices/${id}/disconnect`)
}

// --- Pairing requests ---

export function listPairRequests(status = 'pending') {
  return client.get('/devices/pair-requests', { params: { status } })
}

export function approvePairRequest(requestId) {
  return client.post(`/devices/pair-requests/${requestId}/approve`)
}

export function rejectPairRequest(requestId) {
  return client.post(`/devices/pair-requests/${requestId}/reject`)
}
