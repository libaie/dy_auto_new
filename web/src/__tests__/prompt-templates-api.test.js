import { describe, it, expect, vi, beforeEach } from 'vitest'
import { streamTemplateRewrite } from '../api/promptTemplates.js'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  handleUnauthorizedResponse: vi.fn(),
}))

vi.mock('../api/client.js', () => ({
  default: {
    get: mocks.get,
    post: mocks.post,
    put: mocks.put,
    patch: mocks.patch,
    delete: mocks.delete,
  },
  handleUnauthorizedResponse: mocks.handleUnauthorizedResponse,
}))

function streamFrom(chunks) {
  const encoder = new TextEncoder()

  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
}

describe('prompt template SSE API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
    localStorage.setItem('token', 'test-token')
  })

  it('streamTemplateRewrite posts with bearer token and parses split SSE frames', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamFrom([
        'data: {"type":"delta","text":"Hel',
        'lo"}\n\n',
        'data: {"type":"done"}',
      ]),
    })
    vi.stubGlobal('fetch', fetchMock)
    const events = []

    await streamTemplateRewrite({ template: 'old' }, { onEvent: (event) => events.push(event) })

    expect(fetchMock).toHaveBeenCalledWith('/api/prompt-templates/rewrite-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer test-token',
      },
      body: JSON.stringify({ template: 'old' }),
    })
    expect(events).toEqual([
      { type: 'delta', text: 'Hello' },
      { type: 'done' },
    ])
  })

  it('throws parsed detail for non-ok responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: vi.fn().mockResolvedValue({ detail: 'Invalid prompt' }),
    }))

    await expect(streamTemplateRewrite({ template: 'old' })).rejects.toThrow('Invalid prompt')
  })

  it('calls the shared unauthorized handler and throws parsed detail for 401 responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: vi.fn().mockResolvedValue({ detail: 'Please log in' }),
    }))

    await expect(streamTemplateRewrite({ template: 'old' })).rejects.toThrow('Please log in')
    expect(mocks.handleUnauthorizedResponse).toHaveBeenCalledTimes(1)
  })

  it('forwards SSE error events before rejecting', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamFrom(['data: {"type":"error","message":"Rewrite failed"}\n\n']),
    }))
    const events = []

    await expect(
      streamTemplateRewrite({ template: 'old' }, { onEvent: (event) => events.push(event) })
    ).rejects.toThrow('Rewrite failed')
    expect(events).toEqual([{ type: 'error', message: 'Rewrite failed' }])
  })

  it('awaits async onEvent handlers before resolving', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamFrom(['data: {"type":"done"}\n\n']),
    }))
    const order = []

    const streamPromise = streamTemplateRewrite({ template: 'old' }, {
      onEvent: async (event) => {
        order.push(`start:${event.type}`)
        await Promise.resolve()
        order.push(`finish:${event.type}`)
      },
    }).then(() => order.push('resolved'))

    await streamPromise

    expect(order).toEqual(['start:done', 'finish:done', 'resolved'])
  })

  it('rejects when async onEvent rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamFrom(['data: {"type":"done"}\n\n']),
    }))

    await expect(
      streamTemplateRewrite({ template: 'old' }, {
        onEvent: async () => {
          await Promise.resolve()
          throw new Error('handler failed')
        },
      })
    ).rejects.toThrow('handler failed')
  })

  it('parses CRLF-delimited SSE frames', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: streamFrom([
        'data: {"type":"delta","text":"Hello"}\r\n\r\n',
        'data: {"type":"done"}\r\n\r\n',
      ]),
    }))
    const events = []

    await streamTemplateRewrite({ template: 'old' }, { onEvent: (event) => events.push(event) })

    expect(events).toEqual([
      { type: 'delta', text: 'Hello' },
      { type: 'done' },
    ])
  })
})
