import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SeriesDetailPage from '../views/SeriesDetailPage.vue'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  startPipeline: vi.fn(),
  autoPlanEpisode: vi.fn(),
  listRuns: vi.fn(() => Promise.resolve({ data: { ok: true, runs: [] } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'sid' } }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('../api/series.js', () => ({
  getSeries: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      series: {
        id: 'sid',
        title: 'City Healer',
        logline: 'One sentence story',
        total_episodes: 1,
        genre: 'drama',
        mode: 'fully_automatic',
        target_duration: 60,
      },
      episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'done', duration_seconds: 5 }],
    },
  })),
  getStyleLock: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      locked: true,
      version: 2,
      missing_assets: [],
      reference_status: {
        characters: { ready: 1, total: 1 },
        scenes: { ready: 1, total: 1 },
      },
      agency_team_status: {
        enabled: true,
        version: '2026-05-21.1',
        core_role_count: 5,
        support_role_count: 4,
      },
    },
  })),
  lockSeriesStyle: vi.fn(),
  autoGenerateAssets: vi.fn(),
}))

vi.mock('../api/director.js', () => ({
  autoPlanEpisode: mocks.autoPlanEpisode,
}))

vi.mock('../api/pipeline.js', () => ({
  listRuns: mocks.listRuns,
  startPipeline: mocks.startPipeline,
}))

describe('SeriesDetailPage agency team status', () => {
  beforeEach(() => {
    mocks.push.mockClear()
    mocks.startPipeline.mockClear()
    mocks.autoPlanEpisode.mockClear()
    mocks.listRuns.mockReset()
    mocks.listRuns.mockResolvedValue({ data: { ok: true, runs: [] } })
  })

  it('shows embedded expert team readiness from style lock status', async () => {
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('专家团队')
    expect(wrapper.text()).toContain('5 核心')
    expect(wrapper.text()).toContain('4 支援')
  })

  it('does not restart a completed episode when every episode is done', async () => {
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.findAll('button').find(btn => btn.text().includes('全部剧集已完成'))
    expect(button).toBeTruthy()
    expect(button.attributes('disabled')).toBeDefined()

    await button.trigger('click')
    expect(mocks.autoPlanEpisode).not.toHaveBeenCalled()
    expect(mocks.startPipeline).not.toHaveBeenCalled()
  })

  it('still renders series details when optional pipeline history is unavailable', async () => {
    mocks.listRuns.mockRejectedValue({ response: { status: 404, data: { detail: 'Not Found' } } })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('City Healer')
    expect(wrapper.text()).not.toContain('Request failed with status code 404')
  })
})
