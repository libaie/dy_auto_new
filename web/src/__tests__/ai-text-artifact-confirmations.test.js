import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AITextArtifactWorkbenchPage from '../views/AITextArtifactWorkbenchPage.vue'

const mocks = vi.hoisted(() => ({
  listAITextArtifacts: vi.fn(),
  approveAITextArtifact: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  regenerateAITextArtifact: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { seriesId: 'sid' }, query: {} }),
}))

vi.mock('../api/aiTextArtifacts.js', () => ({
  listAITextArtifacts: mocks.listAITextArtifacts,
  editAITextArtifact: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  approveAITextArtifact: mocks.approveAITextArtifact,
  regenerateAITextArtifact: mocks.regenerateAITextArtifact,
}))

function artifact() {
  return {
    id: 'artifact-1',
    artifact_type: 'episode_script',
    version: 1,
    status: 'review_pending',
    source_type: 'ai',
    content_text: 'AI script body',
    content_json: { scenes: [] },
    input_json: { prompt: 'write script' },
    model_trace_json: { provider: 'test-llm' },
    review_trace_json: {},
  }
}

describe('AITextArtifactWorkbenchPage confirmations', () => {
  let confirmSpy

  beforeEach(() => {
    vi.clearAllMocks()
    confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    mocks.listAITextArtifacts.mockResolvedValue({
      data: { ok: true, artifacts: [artifact()] },
    })
  })

  afterEach(() => {
    confirmSpy.mockRestore()
  })

  it('does not approve or regenerate when the user cancels confirmation', async () => {
    const wrapper = mount(AITextArtifactWorkbenchPage)
    await flushPromises()

    await wrapper.find('[data-test="artifact-approve"]').trigger('click')
    await wrapper.find('[data-test="artifact-regenerate"]').trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalledTimes(2)
    expect(mocks.approveAITextArtifact).not.toHaveBeenCalled()
    expect(mocks.regenerateAITextArtifact).not.toHaveBeenCalled()
  })
})
