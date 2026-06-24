import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AITextArtifactWorkbenchPage from '../views/AITextArtifactWorkbenchPage.vue'

const mocks = vi.hoisted(() => ({
  listAITextArtifacts: vi.fn(),
  editAITextArtifact: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  approveAITextArtifact: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  regenerateAITextArtifact: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

function artifact(overrides = {}) {
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
    ...overrides,
  }
}

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { seriesId: 'sid' }, query: {} }),
}))

vi.mock('../api/aiTextArtifacts.js', () => ({
  listAITextArtifacts: mocks.listAITextArtifacts,
  editAITextArtifact: mocks.editAITextArtifact,
  approveAITextArtifact: mocks.approveAITextArtifact,
  regenerateAITextArtifact: mocks.regenerateAITextArtifact,
}))

describe('AITextArtifactWorkbenchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listAITextArtifacts.mockResolvedValue({
      data: {
        ok: true,
        artifacts: [artifact()],
      },
    })
  })

  it('shows AI text output, trace data, and mutation actions', async () => {
    const wrapper = mount(AITextArtifactWorkbenchPage)
    await flushPromises()

    expect(wrapper.text()).toContain('AI 文本追溯台')
    expect(wrapper.text()).toContain('episode_script')
    expect(wrapper.text()).toContain('AI script body')
    expect(wrapper.text()).toContain('test-llm')

    await wrapper.find('[data-test="artifact-edit-input"]').setValue('Human edit body')
    await wrapper.find('[data-test="artifact-save-edit"]').trigger('click')
    await flushPromises()

    expect(mocks.editAITextArtifact).toHaveBeenCalledWith('artifact-1', {
      content_text: 'Human edit body',
      content_json: { scenes: [] },
    })

    await wrapper.find('[data-test="artifact-approve"]').trigger('click')
    await flushPromises()
    expect(mocks.approveAITextArtifact).toHaveBeenCalledWith('artifact-1')

    await wrapper.find('[data-test="artifact-regenerate-input"]').setValue('Make the hook sharper')
    await wrapper.find('[data-test="artifact-regenerate"]').trigger('click')
    await flushPromises()
    expect(mocks.regenerateAITextArtifact).toHaveBeenCalledWith('artifact-1', {
      input_json: {
        reason: 'manual_regenerate_request',
        instruction: 'Make the hook sharper',
      },
    })
  })

  it('selects the edited child version before approving', async () => {
    const edited = artifact({
      id: 'artifact-2',
      version: 2,
      source_type: 'human_edit',
      content_text: 'Human edit body',
      parent_artifact_id: 'artifact-1',
    })
    mocks.editAITextArtifact.mockResolvedValueOnce({ data: { ok: true, artifact: edited } })
    mocks.listAITextArtifacts
      .mockResolvedValueOnce({ data: { ok: true, artifacts: [artifact()] } })
      .mockResolvedValueOnce({ data: { ok: true, artifacts: [edited, artifact()] } })
      .mockResolvedValueOnce({ data: { ok: true, artifacts: [{ ...edited, status: 'approved' }, artifact({ status: 'superseded' })] } })
    const wrapper = mount(AITextArtifactWorkbenchPage)
    await flushPromises()

    await wrapper.find('[data-test="artifact-edit-input"]').setValue('Human edit body')
    await wrapper.find('[data-test="artifact-save-edit"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="artifact-approve"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('v2')
    expect(mocks.approveAITextArtifact).toHaveBeenCalledWith('artifact-2')
  })

  it('selects the regenerated child version before approving', async () => {
    const regenerated = artifact({
      id: 'artifact-regen-2',
      version: 2,
      source_type: 'ai_regenerate',
      content_text: 'Regenerated AI body',
      parent_artifact_id: 'artifact-1',
    })
    mocks.regenerateAITextArtifact.mockResolvedValueOnce({ data: { ok: true, artifact: regenerated } })
    mocks.listAITextArtifacts
      .mockResolvedValueOnce({ data: { ok: true, artifacts: [artifact()] } })
      .mockResolvedValueOnce({ data: { ok: true, artifacts: [regenerated, artifact()] } })
      .mockResolvedValueOnce({ data: { ok: true, artifacts: [{ ...regenerated, status: 'approved' }, artifact({ status: 'superseded' })] } })
    const wrapper = mount(AITextArtifactWorkbenchPage)
    await flushPromises()

    await wrapper.find('[data-test="artifact-regenerate-input"]').setValue('Make it sharper')
    await wrapper.find('[data-test="artifact-regenerate"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="artifact-approve"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Regenerated AI body')
    expect(mocks.approveAITextArtifact).toHaveBeenCalledWith('artifact-regen-2')
  })

  it('labels episode artifacts with their episode number and title', async () => {
    mocks.listAITextArtifacts.mockResolvedValueOnce({
      data: {
        ok: true,
        artifacts: [
          artifact({
            id: 'outline-2',
            artifact_type: 'episode_outline',
            target_type: 'episode',
            episode_id: 'episode-2-id',
            content_json: { episode_number: 2, title: 'Second Hook' },
          }),
        ],
      },
    })

    const wrapper = mount(AITextArtifactWorkbenchPage)
    await flushPromises()

    expect(wrapper.text()).toContain('episode_outline · E02 · Second Hook')
    expect(wrapper.text()).toContain('E02 · Second Hook')
  })

  it('lists asset director plan artifacts', async () => {
    mocks.listAITextArtifacts.mockResolvedValueOnce({
      data: {
        ok: true,
        artifacts: [
          artifact({
            id: 'asset-director-1',
            artifact_type: 'asset_director_plan',
            target_type: 'series',
            target_id: 'sid',
            content_text: '资产导演计划',
            content_json: { readiness: { status: 'ready' } },
          }),
        ],
      },
    })

    const wrapper = mount(AITextArtifactWorkbenchPage)
    await flushPromises()

    expect(wrapper.text()).toContain('asset_director_plan')
    expect(wrapper.text()).toContain('资产导演计划')
  })
})
