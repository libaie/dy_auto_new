import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'

describe('AutoRepairSummaryStrip', () => {
  it('summarizes repair totals and manual gates in Chinese', () => {
    const wrapper = mount(AutoRepairSummaryStrip, {
      props: {
        summary: { total: 3, active: 1, manual_required: 1, estimated_cost: 0.8 },
      },
    })

    expect(wrapper.text()).toContain('自动返修')
    expect(wrapper.text()).toContain('全部 3')
    expect(wrapper.text()).toContain('进行中 1')
    expect(wrapper.text()).toContain('需人工 1')
    expect(wrapper.text()).toContain('预计 0.80 元')
    expect(wrapper.text()).not.toMatch(/Provider|Task|宸茶|閸|锟/)
  })
})
