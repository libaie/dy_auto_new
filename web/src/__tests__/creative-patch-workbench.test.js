import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CreativePatchWorkbench from '../components/agency/CreativePatchWorkbench.vue'

const patches = [{
  id: 'patch-1',
  stage: 'storyboard',
  patch_type: 'storyboard_patch',
  target_type: 'storyboard_frame',
  target_id: 'shot-001',
  title: '强化前三秒钩子',
  reason: '原分镜冲突不够强。',
  before: { image_prompt: '原画面', video_prompt: '原镜头' },
  after: { image_prompt: '新画面', video_prompt: '新镜头' },
  status: 'proposed',
  priority: 'high',
  source_invocation_id: 'inv-1',
}]

describe('CreativePatchWorkbench', () => {
  it('shows patch diff and emits lifecycle actions', async () => {
    const wrapper = mount(CreativePatchWorkbench, {
      props: {
        patches,
        summary: { total: 1, blocking: 1, proposed: 1, edited: 0, approved: 0, applied: 0, rejected: 0 },
      },
    })

    expect(wrapper.text()).toContain('短视频导演台')
    expect(wrapper.text()).toContain('强化前三秒钩子')
    expect(wrapper.text()).toContain('原画面')
    expect(wrapper.text()).toContain('新画面')
    expect(wrapper.text()).toContain('待处理')

    await wrapper.find('button[data-action="approve"]').trigger('click')
    expect(wrapper.emitted('approve')[0][0].id).toBe('patch-1')

    await wrapper.find('button[data-action="apply"]').trigger('click')
    expect(wrapper.emitted('apply')[0][0].id).toBe('patch-1')
  })

  it('edits after fields and emits save', async () => {
    const wrapper = mount(CreativePatchWorkbench, {
      props: {
        patches,
        summary: { total: 1, blocking: 1 },
      },
    })

    const textarea = wrapper.find('textarea[data-field="image_prompt"]')
    await textarea.setValue('人工调整后的画面')
    await wrapper.find('button[data-action="save"]').trigger('click')

    expect(wrapper.emitted('save')[0][0]).toMatchObject({
      id: 'patch-1',
      after: { image_prompt: '人工调整后的画面', video_prompt: '新镜头' },
    })
  })
})
