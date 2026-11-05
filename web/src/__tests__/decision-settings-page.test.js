import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SettingsPage from '../views/SettingsPage.vue'

const api = vi.hoisted(() => ({ getSettings: vi.fn(), updateSettings: vi.fn() }))
const toast = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock('../api/settings.js', () => api)
vi.mock('../api/pixelle.js', () => ({ testConnection: vi.fn() }))
vi.mock('../stores/toast.js', () => ({ useToastStore: () => toast }))

beforeEach(() => {
  vi.clearAllMocks()
  api.getSettings.mockResolvedValue({ data: {
    ai_model: 'deepseek-chat',
    decision_enabled: 'true',
    decision_model: 'typesafe-ai/jev',
    decision_api_url: 'https://ai-gateway.vercel.sh/typesafe/v1/systemone',
    decision_api_key: '****',
    decision_min_confidence: '0.5',
    decision_min_probability: '0.75',
  } })
  api.updateSettings.mockResolvedValue({ data: { updated: 1 } })
})

async function page() {
  const wrapper = mount(SettingsPage)
  await flushPromises()
  return wrapper
}

async function save(wrapper) {
  await wrapper.findAll('button').find(button => button.text() === '保存设置').trigger('click')
  await flushPromises()
}

describe('Jev decision settings', () => {
  it('loads enabled state and preserves a stored credential when saving a blank input', async () => {
    const wrapper = await page()
    expect(wrapper.find('#decision-enabled').element.checked).toBe(true)
    expect(wrapper.find('#decision-api-key').element.value).toBe('')
    expect(wrapper.find('#decision-api-key').attributes('type')).toBe('password')
    await save(wrapper)
    expect(api.updateSettings).toHaveBeenCalledWith(expect.objectContaining({
      ai_model: 'deepseek-chat',
      decision_enabled: 'true',
      decision_model: 'typesafe-ai/jev',
      decision_api_url: 'https://ai-gateway.vercel.sh/typesafe/v1/systemone',
      decision_min_confidence: '0.5',
      decision_min_probability: '0.75',
    }))
    expect(api.updateSettings.mock.calls[0][0]).not.toHaveProperty('decision_api_key')
    wrapper.unmount()
  })

  it.each([
    ['true', true, 'true'],
    [true, true, 'true'],
    ['false', false, 'false'],
    [false, false, 'false'],
    [undefined, true, 'true'],
    ['unknown', true, 'true'],
  ])('preserves safe enabled state %s and valid thresholds on an unrelated recovery save', async (enabled, checked, saved) => {
    api.getSettings.mockResolvedValue({ data: {
      ai_model: 'deepseek-chat',
      ...(enabled === undefined ? {} : { decision_enabled: enabled }),
      decision_model: 'typesafe-ai/jev',
      decision_api_url: 'https://ai-gateway.vercel.sh/typesafe/v1/systemone',
      decision_api_key: '****',
      decision_min_confidence: 'nan',
      decision_min_probability: '0.9',
      decision_config_error: 'Jev 配置无效，请检查服务端环境变量或重新保存决策配置',
    } })
    const wrapper = await page()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(wrapper.find('#decision-enabled').element.checked).toBe(checked)
    expect(wrapper.find('#decision-min-confidence').element.value).toBe('0.5')
    expect(wrapper.find('#decision-min-probability').element.value).toBe('0.9')
    expect(wrapper.find('#decision-api-key').element.value).toBe('')
    expect(wrapper.find('#decision-api-key').attributes('placeholder')).toContain('已配置')

    await wrapper.findAll('input').find(input => input.element.value === 'deepseek-chat').setValue('generation-model-change')
    await save(wrapper)

    expect(api.updateSettings).toHaveBeenCalledWith(expect.objectContaining({
      ai_model: 'generation-model-change',
      decision_enabled: saved,
      decision_min_confidence: '0.5',
      decision_min_probability: '0.9',
    }))
    expect(api.updateSettings.mock.calls[0][0]).not.toHaveProperty('decision_api_key')
    wrapper.unmount()
  })

  it('saves a replacement credential under its own key and clears it after success', async () => {
    const wrapper = await page()
    await wrapper.find('#decision-api-key').setValue('test-only-new-decision-key')
    await save(wrapper)
    expect(api.updateSettings).toHaveBeenCalledWith(expect.objectContaining({
      decision_api_key: 'test-only-new-decision-key', ai_model: 'deepseek-chat',
    }))
    expect(api.updateSettings.mock.calls[0][0]).not.toHaveProperty('ai_api_key')
    expect(wrapper.find('#decision-api-key').element.value).toBe('')
    wrapper.unmount()
  })

  it('sends explicit disable and zero thresholds instead of dropping falsy values', async () => {
    const wrapper = await page()
    await wrapper.find('#decision-enabled').setValue(false)
    await wrapper.find('#decision-min-confidence').setValue(0)
    await wrapper.find('#decision-min-probability').setValue(0)
    await save(wrapper)
    expect(api.updateSettings).toHaveBeenCalledWith(expect.objectContaining({
      decision_enabled: 'false', decision_min_confidence: '0', decision_min_probability: '0',
    }))
    wrapper.unmount()
  })

  it('rejects invalid thresholds before any settings request', async () => {
    const wrapper = await page()
    await wrapper.find('#decision-min-probability').setValue(2)
    await save(wrapper)
    expect(api.updateSettings).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('keeps unsaved input and shows an actionable server configuration failure', async () => {
    api.updateSettings.mockRejectedValue({ response: { data: { detail: '请先配置 ENCRYPTION_KEY' } } })
    const wrapper = await page()
    await wrapper.find('#decision-api-key').setValue('test-only-unsaved-decision-key')
    await save(wrapper)
    expect(wrapper.find('#decision-api-key').element.value).toBe('test-only-unsaved-decision-key')
    expect(toast.error).toHaveBeenCalledWith('请先配置 ENCRYPTION_KEY')
    expect(toast.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
