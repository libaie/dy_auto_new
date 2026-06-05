import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  listModels: vi.fn(() => Promise.resolve({ data: { ok: true, models: [] } })),
  fetchSchema: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      scenes: [
        {
          key: 'script_generation',
          label: 'LLM · 脚本生成',
          model_type: 'llm',
          providers: ['deepseek', 'openai'],
          fields: [
            { key: 'temperature', default: 0.7 },
            { key: 'max_tokens', default: 4096 },
          ],
        },
        {
          key: 'llm_agency_expert_review',
          label: 'LLM · 专家团队审阅',
          model_type: 'llm',
          providers: ['openai', 'openai-compatible'],
          fields: [
            { key: 'temperature', default: 0.2 },
            { key: 'max_tokens', default: 2048 },
            { key: 'protocol', default: 'openai_chat_completions' },
          ],
        },
      ],
      providers: {
        deepseek: { label: 'DeepSeek' },
        openai: { label: 'OpenAI' },
        'openai-compatible': { label: 'OpenAI 兼容接口' },
      },
    },
  })),
  getModel: vi.fn(),
  createModel: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      model: {
        id: 'model-1',
        name: '专家审阅模型',
        model_type: 'llm',
        provider: 'openai',
        api_key_configured: true,
        enabled: true,
        config_json: {
          scene_key: 'llm_agency_expert_review',
          protocol: 'openai_chat_completions',
        },
      },
    },
  })),
  updateModel: vi.fn(),
  deleteModel: vi.fn(),
  testModelConnection: vi.fn(),
}))

vi.mock('../api/aiConfig.js', () => ({
  listModels: mocks.listModels,
  fetchSchema: mocks.fetchSchema,
  getModel: mocks.getModel,
  createModel: mocks.createModel,
  updateModel: mocks.updateModel,
  deleteModel: mocks.deleteModel,
  testModelConnection: mocks.testModelConnection,
}))

describe('AIConfigPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('选择专家团队审阅场景创建模型时写入场景和协议配置', async () => {
    const AIConfigPage = (await import('../views/AIConfigPage.vue')).default
    const wrapper = mount(AIConfigPage, {
      global: {
        stubs: { Teleport: true, Transition: false },
      },
    })
    await flushPromises()

    await wrapper.find('.aicfg-btn-add').trigger('click')
    await flushPromises()

    const sceneSelect = wrapper.findAll('select').find(select =>
      select.find('option[value="llm_agency_expert_review"]').exists()
    )
    expect(sceneSelect).toBeTruthy()
    await sceneSelect.setValue('llm_agency_expert_review')

    await wrapper.find('input').setValue('专家审阅模型')
    await wrapper.find('.aicfg-btn-save').trigger('click')
    await flushPromises()

    expect(mocks.createModel).toHaveBeenCalledTimes(1)
    expect(mocks.createModel).toHaveBeenCalledWith(expect.objectContaining({
      name: '专家审阅模型',
      model_type: 'llm',
      provider: expect.stringMatching(/^(openai|openai-compatible)$/),
      config_json: expect.objectContaining({
        scene_key: 'llm_agency_expert_review',
        protocol: 'openai_chat_completions',
      }),
    }))
  })
})
