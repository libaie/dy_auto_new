// 前端 API 客户端：封装 promptTemplates 相关后端接口，统一给页面和组件调用。
import client, { handleUnauthorizedResponse } from './client.js'

// 入参：includeDisabled 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 listTemplates 对应业务流程的处理结果。
export function listTemplates(includeDisabled = false) {
  return client.get('/prompt-templates', { params: { include_disabled: includeDisabled } })
}

// 前端业务函数：协调 getTemplate 对应的页面流程、接口调用或状态转换。
// 入参：name 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getTemplate 对应业务流程的处理结果。
export function getTemplate(name) {
  return client.get(`/prompt-templates/${name}`)
}

// 前端业务函数：协调 createTemplate 对应的页面流程、接口调用或状态转换。
// 入参：data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 createTemplate 对应业务流程的处理结果。
export function createTemplate(data) {
  return client.post('/prompt-templates', data)
}

// 前端业务函数：协调 updateTemplate 对应的页面流程、接口调用或状态转换。
// 入参：name、data 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateTemplate 对应业务流程的处理结果。
export function updateTemplate(name, data) {
  return client.put(`/prompt-templates/${name}`, data)
}

// 前端业务函数：协调 deleteTemplate 对应的页面流程、接口调用或状态转换。
// 入参：name 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 deleteTemplate 对应业务流程的处理结果。
export function deleteTemplate(name) {
  return client.delete(`/prompt-templates/${name}`)
}

// 前端业务函数：协调 generateTemplate 对应的页面流程、接口调用或状态转换。
// 入参：description、industry 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 generateTemplate 对应业务流程的处理结果。
export function generateTemplate(description, industry = 'health') {
  return client.post('/prompt-templates/generate', { description, industry })
}

// 前端业务函数：协调 toggleTemplate 对应的页面流程、接口调用或状态转换。
// 入参：name、enabled 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 toggleTemplate 对应业务流程的处理结果。
export function toggleTemplate(name, enabled) {
  return client.patch(`/prompt-templates/${name}/toggle`, { enabled })
}

// 前端业务函数：协调 parseErrorMessage 对应的页面流程、接口调用或状态转换。
// 入参：response 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 parseErrorMessage 对应业务流程的处理结果。
async function parseErrorMessage(response) {
  try {
    const data = await response.json()
    return data?.detail || data?.message || response.statusText
  } catch {
    return response.statusText
  }
}

// 前端业务函数：协调 processSseFrame 对应的页面流程、接口调用或状态转换。
// 入参：frame、onEvent 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 processSseFrame 对应业务流程的处理结果。
async function processSseFrame(frame, onEvent) {
  const data = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')

  if (!data) {
    return
  }

  const event = JSON.parse(data)
  if (onEvent) {
    await onEvent(event)
  }
  if (event.type === 'error') {
    throw new Error(event.message || 'Stream error')
  }
}

// 前端业务函数：协调 streamPromptTemplateSse 对应的页面流程、接口调用或状态转换。
// 入参：path、payload 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 streamPromptTemplateSse 对应业务流程的处理结果。
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
    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop()
    for (const frame of frames) {
      await processSseFrame(frame, onEvent)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    await processSseFrame(buffer, onEvent)
  }
}

// 前端业务函数：协调 streamTemplateGeneration 对应的页面流程、接口调用或状态转换。
// 入参：payload、callbacks 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 streamTemplateGeneration 对应业务流程的处理结果。
export function streamTemplateGeneration(payload, callbacks) {
  return streamPromptTemplateSse('/prompt-templates/generate-stream', payload, callbacks)
}

// 前端业务函数：协调 streamTemplateRewrite 对应的页面流程、接口调用或状态转换。
// 入参：payload、callbacks 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 streamTemplateRewrite 对应业务流程的处理结果。
export function streamTemplateRewrite(payload, callbacks) {
  return streamPromptTemplateSse('/prompt-templates/rewrite-stream', payload, callbacks)
}
