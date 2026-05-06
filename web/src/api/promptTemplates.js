import client from './client.js'

export function listTemplates(includeDisabled = false) {
  return client.get('/prompt-templates', { params: { include_disabled: includeDisabled } })
}

export function getTemplate(name) {
  return client.get(`/prompt-templates/${name}`)
}

export function createTemplate(data) {
  return client.post('/prompt-templates', data)
}

export function updateTemplate(name, data) {
  return client.put(`/prompt-templates/${name}`, data)
}

export function deleteTemplate(name) {
  return client.delete(`/prompt-templates/${name}`)
}

export function generateTemplate(description, industry = 'health') {
  return client.post('/prompt-templates/generate', { description, industry })
}

export function toggleTemplate(name, enabled) {
  return client.patch(`/prompt-templates/${name}/toggle`, { enabled })
}
