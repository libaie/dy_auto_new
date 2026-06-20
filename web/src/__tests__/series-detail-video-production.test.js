import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  route: { params: { id: 'sid' }, query: {} },
  getSeries: vi.fn(),
  updateSeries: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  deleteSeries: vi.fn(() => Promise.resolve({ data: { ok: true, action: 'archived' } })),
  unlinkCharacter: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  unlinkScene: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  autoPlanEpisode: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  createVideoProductionRun: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-1' } } })),
  startImageStage: vi.fn(() => Promise.resolve({ data: { ok: true } })),
  startEpisodeProduction: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-1' }, route: '/video-production/run-1' } })),
  getStyleLock: vi.fn(),
  lockSeriesStyle: vi.fn(),
  listAITextArtifacts: vi.fn(() => Promise.resolve({ data: { ok: true, artifacts: [] } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('../api/series.js', () => ({
  getSeries: mocks.getSeries,
  updateSeries: mocks.updateSeries,
  deleteSeries: mocks.deleteSeries,
  unlinkCharacter: mocks.unlinkCharacter,
  unlinkScene: mocks.unlinkScene,
  getStyleLock: mocks.getStyleLock,
  lockSeriesStyle: mocks.lockSeriesStyle,
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
  startEpisodeProduction: mocks.startEpisodeProduction,
}))

vi.mock('../api/aiTextArtifacts.js', () => ({
  listAITextArtifacts: mocks.listAITextArtifacts,
}))

describe('SeriesDetailPage video production launch', () => {
  beforeEach(() => {
    mocks.getSeries.mockReset()
    mocks.getSeries.mockResolvedValue({
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
          pilot_first: true,
          characters: [{
            id: 'char-1',
            name: 'Lin',
            role_type: 'protagonist',
            avatar_front_url: 'https://cdn.test/front.png',
          }, {
            id: 'char-bad',
            name: 'Bad Link Character',
            role_type: 'supporting',
            avatar_front_url: 'javascript:alert(1)',
          }],
          scenes: [{
            id: 'scene-1',
            name: 'Office',
            scene_type: 'indoor',
            reference_wideshot_url: 'https://cdn.test/wide.png',
          }, {
            id: 'scene-bad',
            name: 'Bad Link Scene',
            scene_type: 'indoor',
            reference_wideshot_url: 'http://',
          }],
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
      },
    })
    mocks.push.mockClear()
    mocks.route.params = { id: 'sid' }
    mocks.route.query = {}
    mocks.autoPlanEpisode.mockClear()
    mocks.createVideoProductionRun.mockClear()
    mocks.startImageStage.mockClear()
    mocks.startEpisodeProduction.mockClear()
    mocks.updateSeries.mockClear()
    mocks.deleteSeries.mockClear()
    mocks.unlinkCharacter.mockClear()
    mocks.unlinkScene.mockClear()
    mocks.getStyleLock.mockReset()
    mocks.getStyleLock.mockResolvedValue({
      data: {
        ok: true,
        locked: true,
        status: 'locked',
        version: 1,
        missing_assets: [],
        reference_status: {
          characters: { ready: 1, total: 1 },
          scenes: { ready: 1, total: 1 },
        },
        agency_team_status: { enabled: true, core_role_count: 5, support_role_count: 4 },
      },
    })
    mocks.lockSeriesStyle.mockReset()
    mocks.listAITextArtifacts.mockReset()
    mocks.listAITextArtifacts.mockResolvedValue({ data: { ok: true, artifacts: [] } })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts production through one control-plane action and opens the returned route', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="start-pipeline"]')
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()

    expect(mocks.startEpisodeProduction).toHaveBeenCalledWith({
      series_id: 'sid',
      episode_id: 'ep1',
      target_duration_seconds: 60,
      autostart_images: true,
    })
    expect(mocks.autoPlanEpisode).not.toHaveBeenCalled()
    expect(mocks.createVideoProductionRun).not.toHaveBeenCalled()
    expect(mocks.startImageStage).not.toHaveBeenCalled()
    expect(mocks.push).toHaveBeenCalledWith('/video-production/run-1')
  })

  it('autostarts a fully automatic project opened from creation intent', async () => {
    mocks.route.query = { autostart: 'production' }
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    mount(SeriesDetailPage)
    await flushPromises()
    await flushPromises()

    expect(mocks.startEpisodeProduction).toHaveBeenCalledWith({
      series_id: 'sid',
      episode_id: 'ep1',
      target_duration_seconds: 60,
      autostart_images: true,
    })
    expect(mocks.push).toHaveBeenCalledWith('/video-production/run-1')
  })

  it('does not autostart a step-by-step project opened with creation intent', async () => {
    mocks.route.query = { autostart: 'production' }
    mocks.getSeries.mockResolvedValue({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 1,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 60,
          pilot_first: true,
          characters: [],
          scenes: [],
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
      },
    })
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    mount(SeriesDetailPage)
    await flushPromises()
    await flushPromises()

    expect(mocks.startEpisodeProduction).not.toHaveBeenCalled()
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('skips episodes that already have an active video production run', async () => {
    mocks.getSeries.mockResolvedValue({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 2,
          genre: 'drama',
          mode: 'fully_automatic',
          target_duration: 60,
          pilot_first: true,
          characters: [],
          scenes: [],
        },
        episodes: [
          {
            id: 'ep1',
            episode_number: 1,
            title: 'Pilot',
            status: 'pending',
            active_video_run_id: 'run-old',
            video_run_status: 'image_batch_running',
          },
          { id: 'ep2', episode_number: 2, title: 'Next', status: 'pending' },
        ],
      },
    })
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="start-pipeline"]')
    expect(button).toBeTruthy()
    await button.trigger('click')
    await flushPromises()

    expect(mocks.startEpisodeProduction).toHaveBeenCalledWith({
      series_id: 'sid',
      episode_id: 'ep2',
      target_duration_seconds: 60,
      autostart_images: true,
    })
  })

  it('does not autostart image generation in step-by-step mode', async () => {
    mocks.getSeries.mockResolvedValue({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 1,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 60,
          pilot_first: true,
          characters: [],
          scenes: [],
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
      },
    })
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.find('[data-test="start-pipeline"]').text()).toContain('生成第 1 集')
    await wrapper.find('[data-test="start-pipeline"]').trigger('click')
    await flushPromises()

    expect(mocks.startEpisodeProduction).toHaveBeenCalledWith({
      series_id: 'sid',
      episode_id: 'ep1',
      target_duration_seconds: 60,
      autostart_images: false,
    })
  })

  it('updates series settings from detail page', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="edit-series"]').trigger('click')
    await wrapper.find('[data-test="series-title-input"]').setValue('New Title')
    await wrapper.find('[data-test="save-series"]').trigger('click')
    await flushPromises()

    expect(mocks.updateSeries).toHaveBeenCalledWith('sid', expect.objectContaining({
      title: 'New Title',
      logline: 'One sentence story',
      genre: 'drama',
      target_duration: 60,
      mode: 'fully_automatic',
      pilot_first: true,
    }))
  })

  it('unlinks character from series', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.html()).toContain('https://cdn.test/front.png')
    await wrapper.find('[data-test="unlink-character-char-1"]').trigger('click')
    await flushPromises()

    expect(mocks.unlinkCharacter).toHaveBeenCalledWith('sid', 'char-1')
  })

  it('unlinks scene from series', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.html()).toContain('https://cdn.test/wide.png')
    await wrapper.find('[data-test="unlink-scene-scene-1"]').trigger('click')
    await flushPromises()

    expect(mocks.unlinkScene).toHaveBeenCalledWith('sid', 'scene-1')
  })

  it('renders valid reference links but rejects unsafe reference urls', async () => {
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const validCharacterLink = wrapper.find('a[href="https://cdn.test/front.png"]')
    const validSceneLink = wrapper.find('a[href="https://cdn.test/wide.png"]')

    expect(validCharacterLink.exists()).toBe(true)
    expect(validCharacterLink.find('img').attributes('src')).toBe('https://cdn.test/front.png')
    expect(validSceneLink.exists()).toBe(true)
    expect(validSceneLink.find('img').attributes('src')).toBe('https://cdn.test/wide.png')
    expect(wrapper.html()).not.toContain('javascript:alert')
    expect(wrapper.html()).not.toContain('href="http://"')
    expect(wrapper.html()).not.toContain('src="http://"')
    expect(wrapper.text()).toContain('链接无效')
  })

  it('renders linked secondary reference slots when primary slots are empty', async () => {
    mocks.getSeries.mockResolvedValue({
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
          pilot_first: true,
          characters: [{
            id: 'char-side',
            name: 'Lin',
            role_type: 'protagonist',
            avatar_front_url: '',
            avatar_side_url: 'http://127.0.0.1:8000/static/image-creation/outputs/side.png',
            avatar_threequarter_url: '',
            avatar_fullbody_url: '',
          }],
          scenes: [{
            id: 'scene-mid',
            name: 'Office',
            scene_type: 'indoor',
            reference_wideshot_url: '',
            reference_midshot_url: '/static/image-creation/outputs/mid.png',
            reference_aerial_url: '',
          }],
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
      },
    })
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const sideReference = wrapper.find('[data-test="linked-character-reference-char-side-avatar_side_url"]')
    const midReference = wrapper.find('[data-test="linked-scene-reference-scene-mid-reference_midshot_url"]')

    expect(sideReference.exists()).toBe(true)
    expect(sideReference.attributes('src')).toBe('/static/image-creation/outputs/side.png')
    expect(sideReference.attributes('alt')).toBe('Lin 侧面参考图')
    expect(midReference.exists()).toBe(true)
    expect(midReference.attributes('src')).toBe('/static/image-creation/outputs/mid.png')
    expect(midReference.attributes('alt')).toBe('Office 中景参考图')
  })

  it('renders reference images as soon as style lock progress reports ready slots', async () => {
    mocks.getSeries.mockResolvedValue({
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
          pilot_first: true,
          characters: [{
            id: 'char-live',
            name: 'Lin',
            role_type: 'protagonist',
            avatar_front_url: '',
            avatar_side_url: '',
            avatar_threequarter_url: '',
            avatar_fullbody_url: '',
          }],
          scenes: [{
            id: 'scene-live',
            name: 'Office',
            scene_type: 'indoor',
            reference_wideshot_url: '',
            reference_midshot_url: '',
            reference_aerial_url: '',
          }],
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
      },
    })
    mocks.getStyleLock.mockResolvedValue({
      data: {
        ok: true,
        locked: false,
        status: 'locking',
        version: 2,
        missing_assets: [],
        reference_status: {
          characters: { ready: 1, total: 1 },
          scenes: { ready: 1, total: 1 },
        },
        reference_progress: [{
          asset_type: 'character',
          asset_id: 'char-live',
          asset_name: 'Lin',
          slot: 'avatar_front_url',
          status: 'ready',
          url: '/static/image-creation/outputs/live-front.png',
        }, {
          asset_type: 'scene',
          asset_id: 'scene-live',
          asset_name: 'Office',
          slot: 'reference_midshot_url',
          status: 'ready',
          url: '/static/image-creation/outputs/live-mid.png',
        }],
      },
    })

    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const characterReference = wrapper.find('[data-test="linked-character-reference-char-live-avatar_front_url"]')
    const sceneReference = wrapper.find('[data-test="linked-scene-reference-scene-live-reference_midshot_url"]')

    expect(characterReference.exists()).toBe(true)
    expect(characterReference.attributes('src')).toBe('/static/image-creation/outputs/live-front.png')
    expect(sceneReference.exists()).toBe(true)
    expect(sceneReference.attributes('src')).toBe('/static/image-creation/outputs/live-mid.png')
  })

  it('polls style lock progress and renders each ready reference without a manual refresh', async () => {
    vi.useFakeTimers()
    mocks.getSeries.mockResolvedValue({
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
          pilot_first: true,
          characters: [{
            id: 'char-poll',
            name: 'Lin',
            role_type: 'protagonist',
            avatar_front_url: '',
            avatar_side_url: '',
            avatar_threequarter_url: '',
            avatar_fullbody_url: '',
          }],
          scenes: [],
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending' }],
      },
    })
    mocks.getStyleLock
      .mockResolvedValueOnce({
        data: {
          ok: true,
          locked: false,
          status: 'locking',
          version: 2,
          missing_assets: [],
          reference_status: {
            characters: { ready: 0, total: 1 },
            scenes: { ready: 0, total: 0 },
          },
          reference_progress: [],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ok: true,
          locked: false,
          status: 'locking',
          version: 2,
          missing_assets: [],
          reference_status: {
            characters: { ready: 1, total: 1 },
            scenes: { ready: 0, total: 0 },
          },
          reference_progress: [{
            asset_type: 'character',
            asset_id: 'char-poll',
            asset_name: 'Lin',
            slot: 'avatar_front_url',
            status: 'ready',
            url: '/static/image-creation/outputs/poll-front.png',
          }],
        },
      })

    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.find('[data-test="linked-character-reference-char-poll-avatar_front_url"]').exists()).toBe(false)

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()

    const reference = wrapper.find('[data-test="linked-character-reference-char-poll-avatar_front_url"]')
    expect(reference.exists()).toBe(true)
    expect(reference.attributes('src')).toBe('/static/image-creation/outputs/poll-front.png')
    expect(mocks.getSeries).toHaveBeenCalledTimes(1)
  })

  it('does not submit style lock twice while a lock request is running', async () => {
    let resolveLock
    mocks.lockSeriesStyle.mockImplementation(() => new Promise((resolve) => {
      resolveLock = resolve
    }))
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="lock-style"]')
    await Promise.all([
      button.trigger('click'),
      button.trigger('click'),
    ])

    expect(mocks.lockSeriesStyle).toHaveBeenCalledTimes(1)

    resolveLock({ data: { ok: true, story_bible: { style_lock: { version: 2 } } } })
    await flushPromises()
  })

  it('keeps style lock disabled after refresh while backend reports locking', async () => {
    mocks.getStyleLock.mockResolvedValue({
      data: {
        ok: true,
        locked: false,
        status: 'locking',
        version: 2,
        missing_assets: [],
        reference_status: {
          characters: { ready: 1, total: 1 },
          scenes: { ready: 1, total: 1 },
        },
        agency_team_status: { enabled: true, core_role_count: 5, support_role_count: 4 },
      },
    })
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="lock-style"]')
    expect(button.text()).toContain('锁定中')
    expect(button.attributes('disabled')).toBeDefined()

    await button.trigger('click')
    expect(mocks.lockSeriesStyle).not.toHaveBeenCalled()
  })

  it('does not start production after style lock only schedules a background job', async () => {
    mocks.getStyleLock.mockResolvedValue({
      data: {
        ok: true,
        locked: false,
        status: 'unlocked',
        version: 0,
        missing_assets: [],
        reference_status: {
          characters: { ready: 0, total: 1 },
          scenes: { ready: 0, total: 1 },
        },
        agency_team_status: { enabled: true, core_role_count: 5, support_role_count: 4 },
      },
    })
    mocks.lockSeriesStyle.mockResolvedValue({
      data: {
        ok: true,
        status: 'locking',
        story_bible: { style_lock: { status: 'locking', locked: false, version: 1 } },
      },
    })
    const SeriesDetailPage = (await import('../views/SeriesDetailPage.vue')).default
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="start-pipeline"]')
    await button.trigger('click')
    await flushPromises()

    expect(mocks.lockSeriesStyle).toHaveBeenCalledTimes(1)
    expect(mocks.startEpisodeProduction).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('风格锁定正在后台执行')
  })
})
