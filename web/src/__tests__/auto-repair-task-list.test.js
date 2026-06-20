import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AutoRepairTaskList from '../components/agency/AutoRepairTaskList.vue'

describe('AutoRepairTaskList', () => {
  it('renders readable repair context and emits actions', async () => {
    const wrapper = mount(AutoRepairTaskList, {
      props: {
        tasks: [{
          id: 'job-1',
          type: 'storyboard_missing_references',
          status: 'blocked',
          reason: '分镜缺少角色参考图',
          expected_result: '补齐后重新进入分镜审查',
          repair_action_label: '去分镜处理',
          repair_route: '/series/s1',
          affected_ids: ['shot-1'],
          estimated_cost: 0,
          retry_actions: { retry_enabled: true, primary_label: '重试返修' },
        }],
      },
    })

    expect(wrapper.text()).toContain('分镜参考信息缺失')
    expect(wrapper.text()).toContain('分镜缺少角色参考图')
    expect(wrapper.text()).toContain('完成返修后重新进入质量门')
    expect(wrapper.text()).not.toContain('等待下一步处理')
    expect(wrapper.text()).toContain('重试返修')
    expect(wrapper.text()).not.toMatch(/瀹歌尪|闁|閸|锟|\?{3,}/)

    await wrapper.findAll('button').find(button => button.text().includes('重试返修')).trigger('click')
    await wrapper.findAll('button').find(button => button.text().includes('去分镜处理')).trigger('click')

    expect(wrapper.emitted('retry')?.[0]?.[0].id).toBe('job-1')
    expect(wrapper.emitted('manual-action')?.[0]?.[0].id).toBe('job-1')
  })

  it('does not render a fake manual route when route is missing', () => {
    const wrapper = mount(AutoRepairTaskList, {
      props: {
        tasks: [{
          id: 'job-2',
          type: 'manual_incomplete_repair_task',
          status: 'blocked',
          reason: '专家审查结果缺少可执行结论，需要人工确认',
          retry_actions: { retry_enabled: false },
        }],
      },
    })

    expect(wrapper.text()).toContain('暂无可跳转入口')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('collapses long task lists until the user expands them', async () => {
    const tasks = Array.from({ length: 7 }, (_, index) => ({
      id: `job-${index}`,
      type: 'image_generation_failed',
      status: 'blocked',
      reason: `第 ${index + 1} 条图像返修`,
      retry_actions: { retry_enabled: false },
    }))
    const wrapper = mount(AutoRepairTaskList, {
      props: { tasks, initialVisibleCount: 3 },
    })

    expect(wrapper.text()).toContain('第 1 条图像返修')
    expect(wrapper.text()).not.toContain('第 7 条图像返修')
    await wrapper.findAll('button').find(button => button.text().includes('展开全部')).trigger('click')
    expect(wrapper.text()).toContain('第 7 条图像返修')
  })

  it('requires explicit reason before paid retry authorization', async () => {
    const wrapper = mount(AutoRepairTaskList, {
      attachTo: document.body,
      props: {
        tasks: [{
          id: 'paid-job',
          type: 'image_generation_timeout',
          status: 'blocked',
          reason: '模型任务超时',
          estimated_cost: 2.5,
          retry_actions: { paid_authorization_required: true, primary_label: '确认追加预算并重试' },
        }],
      },
    })

    await wrapper.findAll('button').find(button => button.text().includes('确认追加预算并重试')).trigger('click')
    expect(wrapper.text()).toContain('确认付费返修')

    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.text()).toContain('请填写确认原因')

    await wrapper.find('textarea').setValue('人工确认本次返修预算')
    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.emitted('retry')?.[0]?.[0].id).toBe('paid-job')
    expect(wrapper.emitted('retry')?.[0]?.[1]).toMatchObject({
      reason: '人工确认本次返修预算',
      budget_delta: 2.5,
      confirmed_budget_delta: 2.5,
    })

    wrapper.unmount()
  })
})
