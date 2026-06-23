import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getSeries: vi.fn(),
  ensureSeriesEpisodes: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  generateSeriesStoryPlan: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  generateEpisodeScript: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  updateSeries: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  deleteSeries: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
  unlinkCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  unlinkScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  getStyleLock: vi.fn(() => Promise.resolve({
    data: {
      ok: true,
      locked: true,
      status: 'locked',
      version: 1,
      missing_assets: [],
      reference_status: {
        characters: { ready: 0, total: 0 },
        scenes: { ready: 0, total: 0 },
      },
    },
  })),
  lockSeriesStyle: vi.fn(),
  autoGenerateAssets: vi.fn(),
  listRuns: vi.fn(() => Promise.resolve({ data: { ok: true, runs: [] } })),
  startEpisodeProduction: vi.fn(() => Promise.resolve({ data: { ok: true, route: '/video-production/run-1' } })),
  listAITextArtifacts: vi.fn(() => Promise.resolve({ data: { ok: true, artifacts: [] } })),
  getStoryboardImageState: vi.fn(() => Promise.resolve({ data: { ok: true, frames: [], frames_by_id: {}, summary: {} } })),
  createMissingStoryboardImageTasks: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  createStoryboardFrameImageTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'sid' }, query: {} }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('../api/series.js', () => ({
  getSeries: mocks.getSeries,
  ensureSeriesEpisodes: mocks.ensureSeriesEpisodes,
  generateSeriesStoryPlan: mocks.generateSeriesStoryPlan,
  generateEpisodeScript: mocks.generateEpisodeScript,
  updateSeries: mocks.updateSeries,
  deleteSeries: mocks.deleteSeries,
  unlinkCharacter: mocks.unlinkCharacter,
  unlinkScene: mocks.unlinkScene,
  getStyleLock: mocks.getStyleLock,
  lockSeriesStyle: mocks.lockSeriesStyle,
  autoGenerateAssets: mocks.autoGenerateAssets,
}))

vi.mock('../api/pipeline.js', () => ({
  listRuns: mocks.listRuns,
}))

vi.mock('../api/videoProduction.js', () => ({
  startEpisodeProduction: mocks.startEpisodeProduction,
}))

vi.mock('../api/aiTextArtifacts.js', () => ({
  listAITextArtifacts: mocks.listAITextArtifacts,
}))

vi.mock('../api/storyboardImages.js', () => ({
  getStoryboardImageState: mocks.getStoryboardImageState,
  createMissingStoryboardImageTasks: mocks.createMissingStoryboardImageTasks,
  createStoryboardFrameImageTask: mocks.createStoryboardFrameImageTask,
}))

function seriesPayload() {
  return {
    data: {
      ok: true,
      series: {
        id: 'sid',
        title: 'City Healer',
        logline: 'One sentence story',
        total_episodes: 2,
        genre: 'drama',
        mode: 'step_by_step',
        target_duration: 30,
        characters: [],
        scenes: [],
      },
      episodes: [
        { id: 'ep1', episode_number: 1, title: 'Pilot', status: 'completed' },
        { id: 'ep2', episode_number: 2, title: 'Second', status: 'done' },
      ],
    },
  }
}

describe('SeriesDetailPage text backfill', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getSeries.mockResolvedValue(seriesPayload())
  })

  it('backfills every completed episode missing script and storyboard in one run', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="start-pipeline"]')
    expect(button.text()).toContain('补齐 2 集剧本/分镜')

    await button.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(mocks.generateEpisodeScript).toHaveBeenNthCalledWith(1, 'sid', 'ep1', { target_duration_seconds: 30 })
    expect(mocks.generateEpisodeScript).toHaveBeenNthCalledWith(2, 'sid', 'ep2', { target_duration_seconds: 30 })
    expect(mocks.getSeries).toHaveBeenCalledTimes(2)
    expect(mocks.startEpisodeProduction).not.toHaveBeenCalled()
  })

  it('allows force story planning when every episode repeats the full asset pool', async () => {
    mocks.getSeries.mockResolvedValue({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 2,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 30,
          story_bible_json: { story_planning: { status: 'completed', version: 1 } },
          characters: [{ id: 'char-1' }, { id: 'char-2' }],
          scenes: [{ id: 'scene-1' }, { id: 'scene-2' }],
        },
        episodes: [
          {
            id: 'ep1',
            episode_number: 1,
            title: 'Pilot',
            status: 'pending',
            asset_scope: { character_ids: ['char-1', 'char-2'], scene_ids: ['scene-1', 'scene-2'] },
          },
          {
            id: 'ep2',
            episode_number: 2,
            title: 'Second',
            status: 'pending',
            asset_scope: { character_ids: ['char-1', 'char-2'], scene_ids: ['scene-1', 'scene-2'] },
          },
        ],
      },
    })

    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="generate-story-plan"]')
    expect(button.text()).toContain('重建分集角色/场景规划')
    expect(wrapper.find('[data-test="story-plan-status"]').text()).toContain('分集角色/场景重复')

    await button.trigger('click')
    await flushPromises()

    expect(mocks.generateSeriesStoryPlan).toHaveBeenCalledWith('sid', { force: true })
  })
})
