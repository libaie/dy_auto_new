import client, { handleUnauthorizedResponse } from './client.js'

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

async function parseErrorMessage(response) {
  try {
    const data = await response.json()
    return data?.detail || data?.message || response.statusText
  } catch {
    return response.statusText
  }
}

function processSseFrame(frame, onEvent) {
  const data = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')

  if (!data) {
    return
  }

  const event = JSON.parse(data)
  if (onEvent) {
    onEvent(event)
  }
  if (event.type === 'error') {
    throw new Error(event.message || 'Stream error')
  }
}

export async function streamPromptTemplateSse(path, payload, { onEvent } = {}) {
  const token = localStorage.getItem('token')
  const headers = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`/api${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const message = await parseErrorMessage(response)
    if (response.status === 401) {
      handleUnauthorizedResponse()
    }
    throw new Error(message)
  }

  if (!response.body) {
    throw new Error('Streaming response body is unavailable')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop()
    frames.forEach((frame) => processSseFrame(frame, onEvent))
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    processSseFrame(buffer, onEvent)
  }
}

export function streamTemplateGeneration(payload, callbacks) {
  return streamPromptTemplateSse('/prompt-templates/generate-stream', payload, callbacks)
}

export function streamTemplateRewrite(payload, callbacks) {
  return streamPromptTemplateSse('/prompt-templates/rewrite-stream', payload, callbacks)
}
