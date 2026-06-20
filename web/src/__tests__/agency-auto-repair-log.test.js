import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AgencyDecisionLog from '../components/agency/AgencyDecisionLog.vue'

describe('AgencyDecisionLog auto repair transparency', () => {
  it('shows repair finding, action, cost, and next gate in Chinese', () => {
    const wrapper = mount(AgencyDecisionLog, {
      props: {
        items: [{
          invocation_id: 'inv-1',
          stage: 'storyboard',
          expert_id: 'storyboard_quality_reviewer',
          result_status: 'warning',
          decision: 'warning',
          findings: ['分镜缺少角色参考图'],
          repair_tasks: [{
            id: 'repair-job-1',
            type: 'storyboard_missing_references',
            status: 'blocked',
            reason: '分镜缺少角色参考图',
            expected_result: '补齐后重新进入审查',
            repair_action_label: '去系列详情补分镜参考',
            estimated_cost: 0,
            retry_actions: { retry_enabled: true, primary_label: '重试返修' },
          }],
        }],
        stages: [{ stage: 'storyboard', label: '分镜脚本' }],
        expertTeam: [{ expert_id: 'storyboard_quality_reviewer', name: '分镜脚本质量审查专家' }],
      },
    })

    expect(wrapper.text()).toContain('决策日志')
    expect(wrapper.text()).toContain('分镜脚本')
    expect(wrapper.text()).toContain('分镜缺少角色参考图')
    expect(wrapper.text()).toContain('返修动作')
    expect(wrapper.text()).toContain('完成返修后重新进入质量门')
    expect(wrapper.text()).not.toMatch(/Invalid JSON|Provider|宸茶|閸|锟/)
  })
})
