import client from './client.js'

export function getDashboard() {
  return client.get('/stats/dashboard')
}

export function getDailyStats(date) {
  return client.get('/stats/daily', { params: { date } })
}

export function getAccountStats(accountId) {
  return client.get(`/stats/accounts/${accountId}`)
}

export function getRealtimeStats() {
  return client.get('/stats/realtime')
}
