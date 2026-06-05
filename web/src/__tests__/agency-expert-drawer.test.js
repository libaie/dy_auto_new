import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import AgencyExpertDrawer from '../components/agency/AgencyExpertDrawer.vue'
import { getAgencyExpert } from '../api/agency.js'

vi.mock('../api/agency.js', () => ({
  getAgencyExpert: vi.fn(() => Promise.resolve({
    data: {
      expert_id: 'prompt_engineer',
      name: '提示词工程师',
      source_path: 'specialized/prompt-engineer.md',
      source_commit: '13b8800',
      sha256: 'abc123',
      markdown: '# 提示词工程师\n\n负责把故事意图拆解为稳定提示词。',
    },
  })),
}))

enableAutoUnmount(afterEach)

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AgencyExpertDrawer', () => {
  it('loads expert detail with markdown and source metadata', async () => {
    const wrapper = mount(AgencyExpertDrawer, {
      props: { expertId: 'prompt_engineer' },
    })

    await flushPromises()

    expect(getAgencyExpert).toHaveBeenCalledWith('prompt_engineer')
    expect(wrapper.text()).toContain('提示词工程师')
    expect(wrapper.text()).toContain('源文件')
    expect(wrapper.text()).toContain('已记录源文件')
    expect(wrapper.text()).toContain('已记录源提交')
    expect(wrapper.text()).toContain('已记录校验信息')
    expect(wrapper.text()).not.toContain('specialized/prompt-engineer.md')
    expect(wrapper.text()).toContain('负责把故事意图拆解为稳定提示词')
    expect(wrapper.text()).toContain('关闭')
    expect(wrapper.text()).not.toContain('Prompt Engineer')
  })

  it('exposes dialog semantics and closes on Escape', async () => {
    const opener = document.createElement('button')
    document.body.appendChild(opener)
    opener.focus()

    const wrapper = mount(AgencyExpertDrawer, {
      props: { expertId: 'prompt_engineer' },
      attachTo: document.body,
    })

    await flushPromises()
    const dialog = wrapper.get('[role="dialog"]')

    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.attributes('aria-labelledby')).toBe('agency-expert-drawer-title')
    expect(wrapper.get('#agency-expert-drawer-title').text()).toContain('提示词工程师')

    opener.focus()
    expect(document.activeElement).toBe(opener)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(1)

    wrapper.unmount()
    opener.remove()
  })

  it('emits close from the Chinese close button', async () => {
    const wrapper = mount(AgencyExpertDrawer, {
      props: { expertId: 'prompt_engineer' },
    })

    await flushPromises()
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('shows a localized error instead of raw backend messages', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    getAgencyExpert.mockRejectedValueOnce(new Error('Network Error: Failed to fetch expert profile'))

    const wrapper = mount(AgencyExpertDrawer, {
      props: { expertId: 'prompt_engineer' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('专家档案加载失败，请稍后重试。')
    expect(wrapper.text()).not.toMatch(/Network Error|Failed to fetch|expert profile/)
    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })

  it('keeps the current expert when an older request resolves last', async () => {
    let resolveExpertA
    let resolveExpertB
    const expertAPromise = new Promise((resolve) => {
      resolveExpertA = resolve
    })
    const expertBPromise = new Promise((resolve) => {
      resolveExpertB = resolve
    })

    getAgencyExpert.mockImplementation((expertId) => {
      if (expertId === 'expert_a') return expertAPromise
      if (expertId === 'expert_b') return expertBPromise
      return Promise.reject(new Error(`Unexpected expert id: ${expertId}`))
    })

    const wrapper = mount(AgencyExpertDrawer, {
      props: { expertId: 'expert_a' },
    })
    await flushPromises()

    await wrapper.setProps({ expertId: 'expert_b' })
    await flushPromises()

    resolveExpertB({
      data: {
        expert_id: 'expert_b',
        name: 'Expert B',
        source_path: 'experts/b.md',
        source_commit: 'commit-b',
        sha256: 'sha-b',
        markdown: '# Expert B\n\nCurrent expert content.',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Expert B')
    expect(wrapper.text()).toContain('Current expert content.')
    expect(wrapper.text()).not.toContain('Expert A')
    expect(wrapper.text()).not.toContain('Stale expert content.')

    resolveExpertA({
      data: {
        expert_id: 'expert_a',
        name: 'Expert A',
        source_path: 'experts/a.md',
        source_commit: 'commit-a',
        sha256: 'sha-a',
        markdown: '# Expert A\n\nStale expert content.',
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Expert B')
    expect(wrapper.text()).toContain('Current expert content.')
    expect(wrapper.text()).not.toContain('Expert A')
    expect(wrapper.text()).not.toContain('Stale expert content.')
  })
})
