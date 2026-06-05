import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const lazyState = vi.hoisted(() => ({
  loadCount: 0,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { seriesId: 'sid' } }),
  useRouter: () => ({ back: vi.fn() }),
}))

vi.mock('../api/series.js', () => ({
  getAgencyConsole: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      series: { id: 'sid', title: '城市疗愈师' },
      agency_trace_status: 'completed',
      expert_team: [
        { expert_id: 'prompt_engineer', name: '提示词工程师', phases: ['storyboard'] },
      ],
      stage_graph: [{
        stage: 'storyboard',
        label: '分镜脚本',
        status: 'completed',
        reviewers: [],
        lead: 'prompt_engineer',
        qa: [],
        invocation_ids: [],
      }],
      expert_invocations: [],
      decision_log: [],
      production_steps: [],
    },
  })),
}))

vi.mock('../components/agency/AgencyTeamMap3D.vue', () => {
  lazyState.loadCount += 1
  return {
    __esModule: true,
    default: {
      name: 'AgencyTeamMap3DMock',
      template: '<section data-test="agency-team-map-3d">3D 专家人物化</section>',
    },
  }
})

describe('AgencyConsolePage 3D lazy loading', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  it('loads the 3D team map only after switching to the expert team tab', async () => {
    const { default: AgencyConsolePage } = await import('../views/AgencyConsolePage.vue')
    wrapper = mount(AgencyConsolePage)
    await flushPromises()

    expect(wrapper.find('[data-test="agency-team-map-3d"]').exists()).toBe(false)
    expect(lazyState.loadCount).toBe(0)

    await wrapper.find('button[data-tab="experts"]').trigger('click')
    await flushPromises()

    expect(lazyState.loadCount).toBe(1)
    expect(wrapper.find('[data-test="agency-team-map-3d"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('3D 专家人物化')
  })
})
