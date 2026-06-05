import client from './client.js'

export function listAgencyExperts() {
  return client.get('/agency/experts')
}

export function getAgencyExpert(expertId) {
  return client.get(`/agency/experts/${expertId}`)
}

export function listAgencyInvocations(params) {
  return client.get('/agency/invocations', { params })
}

export function getAgencyInvocation(invocationId) {
  return client.get(`/agency/invocations/${invocationId}`)
}

export function listAgencyRepairTasks(params = {}) {
  return client.get('/agency/repair-tasks', { params })
}

export function retryAgencyRepairTask(jobId) {
  return client.post(`/agency/repair-tasks/${jobId}/retry`)
}

export function authorizeAgencyRepairRetry(jobId, payload) {
  return client.post(`/agency/repair-tasks/${jobId}/authorize-retry`, payload)
}
