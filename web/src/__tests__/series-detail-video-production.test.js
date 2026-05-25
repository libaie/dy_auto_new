import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  autoPlanEpisode: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  createVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-1' } } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
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
      episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
    },
  })),
  getStyleLock: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      locked: true,
      version: 1,
      missing_assets: [],
      reference_status: {
        characters: { ready: 1, total: 1 },
        scenes: { ready: 1, total: 1 },
      },
      agency_team_status: { enabled: true, core_role_count: 5, support_role_count: 4 },
    },
  })),
  lockSeriesStyle: vi.fn(),
  autoGenerateAssets: vi.fn(),
}))

vi.mock('../api/director.js', () => ({
  autoPlanEpisode: mocks.autoPlanEpisode,
}))

vi.mock('../api/pipeline.js', () => ({
  listRuns: vi.fn(() => Promise.resolve({ data: { ok: true, runs: [] } })),
  startPipeline: vi.fn(),
}))

vi.mock('../api/videoProduction.js', () => ({
  createVideoProductionRun: mocks.createVideoProductionRun,
  startImageStage: mocks.startImageStage,
}))

describe('SeriesDetailPage video production launch', () => {
  beforeEach(() => {
    mocks.push.mockClear()
    mocks.autoPlanEpisode.mockClear()
    mocks.createVideoProductionRun.mockClear()
    mocks.startImageStage.mockClear()
  })

  it('creates a staged run after auto-plan and opens the review center', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.findAll('button').find(btn => btn.text().includes('启动'))
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()

    expect(mocks.autoPlanEpisode).toHaveBeenCalledWith('sid', 'ep1', 60)
    expect(mocks.createVideoProductionRun).toHaveBeenCalledWith('sid', 'ep1')
    expect(mocks.startImageStage).toHaveBeenCalledWith('run-1')
    expect(mocks.push).toHaveBeenCalledWith('/video-production/run-1')
  })
})
