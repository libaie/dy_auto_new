import client from './client.js'

export function listSelectors(includeDisabled = false) {
  return client.get('/selectors', { params: { include_disabled: includeDisabled } })
}

export function createSelector(data) {
  return client.post('/selectors', data)
}

export function updateSelector(actionName, data) {
  return client.put(`/selectors/${actionName}`, data)
}

export function deleteSelector(actionName) {
  return client.delete(`/selectors/${actionName}`)
}

export function toggleSelector(actionName, enabled) {
  return client.patch(`/selectors/${actionName}/toggle`, { enabled })
}

export function uploadTemplate(file, actionName) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('action_name', actionName)
  return client.post('/selectors/templates/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function listTemplates() {
  return client.get('/selectors/templates')
}

export function deleteTemplate(filename) {
  return client.delete(`/selectors/templates/${filename}`)
}
