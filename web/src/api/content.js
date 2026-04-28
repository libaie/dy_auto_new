import client from './client.js'

// --- Templates ---
export function listTemplates(params = {}) {
  return client.get('/content/templates', { params })
}

export function getTemplate(id) {
  return client.get(`/content/templates/${id}`)
}

export function createTemplate(data) {
  return client.post('/content/templates', data)
}

export function updateTemplate(id, data) {
  return client.put(`/content/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return client.delete(`/content/templates/${id}`)
}

// --- Sensitive Words ---
export function listSensitiveWords(params = {}) {
  return client.get('/content/sensitive-words', { params })
}

export function addSensitiveWord(word) {
  return client.post('/content/sensitive-words', { word })
}

export function deleteSensitiveWord(id) {
  return client.delete(`/content/sensitive-words/${id}`)
}

// --- AI Generation ---
export function generateContent(templateId, context) {
  return client.post('/content/generate', {
    template_id: templateId,
    context,
  })
}
