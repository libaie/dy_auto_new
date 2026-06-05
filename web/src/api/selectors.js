import client from './client.js'

export function listSelectors(includeDisabled = false, category = '') {
  return client.get('/selectors', { params: { include_disabled: includeDisabled, category: category || undefined } })
}

export function createSelector(data) {
  return client.post('/selectors', data)
}

export function updateSelector(actionName, data) {
  return client.put(`/selectors/${actionName}`, data)
}

export function deleteSelector(actionName, platformVersion, resolutionProfile) {
  var params = {}
  if (platformVersion) params.platform_version = platformVersion
  if (resolutionProfile) params.resolution_profile = resolutionProfile
  return client.delete(`/selectors/${actionName}`, { params })
}

export function toggleSelector(actionName, enabled, platformVersion, resolutionProfile) {
  var params = {}
  if (platformVersion) params.platform_version = platformVersion
  if (resolutionProfile) params.resolution_profile = resolutionProfile
  return client.patch(`/selectors/${actionName}/toggle`, { enabled }, { params })
}

export function uploadTemplate(file, actionName, resolution = 'default') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('action_name', actionName)
  return client.post('/selectors/templates/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { resolution: resolution || 'default' },
  })
}

export function listTemplates() {
  return client.get('/selectors/templates')
}

export function deleteTemplate(filename) {
  return client.delete(`/selectors/templates/${filename}`)
}
export function generateRegex(description) {
  return client.post('/content/generate-regex', { description })
}

export function generateCleanPrompt(description) {
  return client.post('/content/generate-clean-prompt', { description })
}
