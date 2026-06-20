import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SeriesDetailPage from '../views/SeriesDetailPage.vue'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  getSeries: vi.fn(),
  ensureSeriesEpisodes: vi.fn(() => Promise.resolve({ data: { ok: true, created_episode_numbers: [2, 3] } })),
  generateSeriesStoryPlan: vi.fn(() => Promise.resolve({ data: { ok: true, created_episode_numbers: [1] } })),
  generateEpisodeScript: vi.fn(() => Promise.resolve({ data: { ok: true, script: { title: 'Pilot' }, storyboard: { frames: [] } } })),
  startPipeline: vi.fn(),
  startEpisodeProduction: vi.fn(() => Promise.resolve({ data: { ok: true, run: { id: 'run-new' }, route: '/video-production/run-new' } })),
  autoPlanEpisode: vi.fn(),
  listRuns: vi.fn(() => Promise.resolve({ data: { ok: true, runs: [] } })),
  listAITextArtifacts: vi.fn(() => Promise.resolve({ data: { ok: true, artifacts: [] } })),
  getStoryboardImageState: vi.fn(() => Promise.resolve({ data: { ok: true, frames: [], frames_by_id: {}, summary: {} } })),
  createMissingStoryboardImageTasks: vi.fn(() => Promise.resolve({ data: { ok: true, summary: { created: 1 } } })),
  createStoryboardFrameImageTask: vi.fn(() => Promise.resolve({ data: { ok: true } })),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'sid' } }),
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('../api/series.js', () => ({
  getSeries: mocks.getSeries,
  ensureSeriesEpisodes: mocks.ensureSeriesEpisodes,
  generateSeriesStoryPlan: mocks.generateSeriesStoryPlan,
  generateEpisodeScript: mocks.generateEpisodeScript,
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

describe('SeriesDetailPage agency team status', () => {
  beforeEach(() => {
    mocks.push.mockClear()
    mocks.getSeries.mockReset()
    mocks.ensureSeriesEpisodes.mockClear()
    mocks.ensureSeriesEpisodes.mockResolvedValue({ data: { ok: true, created_episode_numbers: [] } })
    mocks.generateSeriesStoryPlan.mockClear()
    mocks.generateSeriesStoryPlan.mockResolvedValue({ data: { ok: true, created_episode_numbers: [1] } })
    mocks.generateEpisodeScript.mockClear()
    mocks.generateEpisodeScript.mockResolvedValue({ data: { ok: true, script: { title: 'Pilot' }, storyboard: { frames: [] } } })
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
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'done', duration_seconds: 5 }],
      },
    })
    mocks.startPipeline.mockClear()
    mocks.startEpisodeProduction.mockClear()
    mocks.autoPlanEpisode.mockClear()
    mocks.listRuns.mockReset()
    mocks.listRuns.mockResolvedValue({ data: { ok: true, runs: [] } })
    mocks.listAITextArtifacts.mockReset()
    mocks.listAITextArtifacts.mockResolvedValue({ data: { ok: true, artifacts: [] } })
    mocks.getStoryboardImageState.mockReset()
    mocks.getStoryboardImageState.mockResolvedValue({ data: { ok: true, frames: [], frames_by_id: {}, summary: {} } })
    mocks.createMissingStoryboardImageTasks.mockReset()
    mocks.createMissingStoryboardImageTasks.mockResolvedValue({ data: { ok: true, summary: { created: 1 } } })
    mocks.createStoryboardFrameImageTask.mockReset()
    mocks.createStoryboardFrameImageTask.mockResolvedValue({ data: { ok: true } })
  })

  it('shows embedded expert team readiness from style lock status', async () => {
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('专家团队')
    expect(wrapper.text()).toContain('5 核心')
    expect(wrapper.text()).toContain('4 支援')
  })

  it('expands an episode to reveal script and storyboard text when present', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          script_json: {
            title: 'Pilot Script',
            scenes: [{ heading: 'Clinic opens', dialogue: ['Lin: We start now.'] }],
          },
          storyboard_json: {
            frames: [{
              frame_id: 'frame-001',
              narration: 'Lin opens the clinic door.',
              image_prompt: 'Warm morning light in a tiny clinic.',
              video_prompt: 'Camera pushes in slowly.',
              duration: 5,
              time_range: '2-4秒',
            }],
          },
        }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')

    expect(wrapper.text()).toContain('Pilot Script')
    expect(wrapper.text()).toContain('Clinic opens')
    expect(wrapper.text()).toContain('Lin opens the clinic door.')
    expect(wrapper.text()).toContain('2-4秒')
    expect(wrapper.text()).toContain('Warm morning light in a tiny clinic.')
    expect(wrapper.text()).toContain('Camera pushes in slowly.')
  })

  it('shows per-episode character and scene assets', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          asset_scope: {
            character_ids: ['char-1'],
            scene_ids: ['scene-1'],
            characters: [{ id: 'char-1', name: 'Scope Lead', source: 'generated', usage: 'Carries the reveal.' }],
            scenes: [{ id: 'scene-1', name: 'Scope Room', source: 'existing', usage: 'Hosts the reveal.' }],
            generated_assets: { characters: [{ name: 'Scope Lead' }], scenes: [] },
          },
        }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')

    expect(wrapper.text()).toContain('本集角色')
    expect(wrapper.text()).toContain('Scope Lead')
    expect(wrapper.text()).toContain('本集场景')
    expect(wrapper.text()).toContain('Scope Room')
    expect(wrapper.text()).toContain('本集新增资产')
    expect(wrapper.text()).toContain('新增')
  })

  it('does not label deduped generated asset specs as newly created', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          asset_scope: {
            character_ids: ['char-1'],
            scene_ids: ['scene-1'],
            characters: [{ id: 'char-1', name: 'Existing Lead', source: 'existing', usage: 'Carries the reveal.' }],
            scenes: [{ id: 'scene-1', name: 'Existing Room', source: 'existing', usage: 'Hosts the reveal.' }],
            generated_assets: { characters: [{ name: 'Existing Lead' }], scenes: [{ name: 'Existing Room' }] },
          },
        }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')

    expect(wrapper.text()).toContain('Existing Lead')
    expect(wrapper.text()).not.toContain('本集新增资产')
    expect(wrapper.text()).not.toContain('新增')
  })

  it('warns when an episode has no scoped assets', async () => {
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')

    expect(wrapper.text()).toContain('缺少本集角色或场景')
  })

  it('prefers the latest approved text artifact over stale episode snapshots', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          script_json: { title: 'Old episode script' },
          storyboard_json: {
            frames: [{
              frame_id: 'old-frame',
              narration: 'Old episode storyboard narration',
              image_prompt: 'Old episode image prompt',
              video_prompt: 'Old episode video prompt',
              duration: 5,
            }],
          },
        }],
      },
    })
    mocks.listAITextArtifacts.mockResolvedValue({
      data: {
        ok: true,
        artifacts: [
          {
            id: 'script-artifact-new',
            episode_id: 'ep1',
            target_type: 'episode',
            artifact_type: 'episode_script',
            status: 'approved',
            version: 2,
            approved_at: '2026-06-12T00:00:00Z',
            content_json: { title: 'Latest approved script' },
          },
          {
            id: 'storyboard-artifact-new',
            episode_id: 'ep1',
            target_type: 'episode',
            artifact_type: 'storyboard',
            status: 'approved',
            version: 2,
            approved_at: '2026-06-12T00:00:00Z',
            content_json: {
              frames: [{
                frame_id: 'new-frame',
                narration: 'Latest approved storyboard narration',
                image_prompt: 'Latest approved image prompt',
                video_prompt: 'Latest approved video prompt',
                duration: 6,
                time_range: '0-6秒',
              }],
            },
          },
        ],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')

    expect(wrapper.text()).toContain('Latest approved script')
    expect(wrapper.text()).toContain('Latest approved storyboard narration')
    expect(wrapper.text()).toContain('0-6秒')
    expect(wrapper.text()).not.toContain('Old episode script')
    expect(wrapper.text()).not.toContain('Old episode storyboard narration')
  })

  it('shows storyboard frame images and can generate missing storyboard images', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          storyboard_json: {
            frames: [{
              frame_id: 'shot-001',
              narration: 'Lin opens the clinic door.',
              image_prompt: 'Warm morning light in a tiny clinic.',
              video_prompt: 'Camera pushes in slowly.',
              duration: 2,
              time_range: '0-2秒',
            }],
          },
        }],
      },
    })
    mocks.getStoryboardImageState.mockResolvedValue({
      data: {
        ok: true,
        summary: { total: 1, approved: 1, missing: 0, pending: 0, running: 0, blocked: 0 },
        frames_by_id: {
          'shot-001': {
            frame_id: 'shot-001',
            time_range: '0-2秒',
            status: 'approved',
            asset: {
              id: 'asset-1',
              url: '/static/image-creation/storyboard-1.png',
              status: 'approved',
              version: 1,
            },
          },
        },
        frames: [],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')
    await flushPromises()

    expect(mocks.getStoryboardImageState).toHaveBeenCalledWith('ep1', { series_id: 'sid' })
    expect(wrapper.text()).toContain('分镜图')
    expect(wrapper.text()).toContain('已通过')
    expect(wrapper.find('img[alt*="0-2秒"]').exists()).toBe(true)

    await wrapper.find('[data-test="generate-missing-storyboard-images-ep1"]').trigger('click')
    await flushPromises()

    expect(mocks.createMissingStoryboardImageTasks).toHaveBeenCalledWith('ep1', { series_id: 'sid' })
  })

  it('passes active production run id to storyboard image calls', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          active_video_run_id: 'run-active',
          storyboard_json: {
            frames: [{
              frame_id: 'shot-001',
              narration: 'Lin opens the clinic door.',
              image_prompt: 'Warm morning light in a tiny clinic.',
              duration: 2,
              time_range: '0-2秒',
            }],
          },
        }],
      },
    })
    mocks.getStoryboardImageState.mockResolvedValue({
      data: {
        ok: true,
        summary: { total: 1, approved: 0, missing: 1, pending: 0, running: 0, blocked: 0 },
        frames_by_id: {},
        frames: [],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="generate-missing-storyboard-images-ep1"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="generate-storyboard-image-ep1-shot-001"]').trigger('click')
    await flushPromises()

    expect(mocks.getStoryboardImageState).toHaveBeenCalledWith('ep1', { series_id: 'sid', run_id: 'run-active' })
    expect(mocks.createMissingStoryboardImageTasks).toHaveBeenCalledWith('ep1', { series_id: 'sid', run_id: 'run-active' })
    expect(mocks.createStoryboardFrameImageTask).toHaveBeenCalledWith('ep1', 'shot-001', { series_id: 'sid', run_id: 'run-active' })
  })

  it('shows an explicit error when approved text artifacts fail to load', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'done',
          script_json: { title: 'Legacy script snapshot' },
        }],
      },
    })
    mocks.listAITextArtifacts.mockRejectedValueOnce({ response: { data: { detail: 'Forbidden' } } })
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('AI 文本加载失败')
    expect(wrapper.text()).toContain('Forbidden')

    await wrapper.find('[data-test="retry-ai-text-artifacts"]').trigger('click')
    await flushPromises()

    expect(mocks.listAITextArtifacts).toHaveBeenCalledTimes(2)
  })

  it('generates a series story plan and shows planning status', async () => {
    const plannedArtifacts = [
      {
        id: 'story-plan-1',
        target_type: 'series',
        artifact_type: 'series_story_plan',
        status: 'approved',
        source_type: 'ai_story_plan',
        version: 1,
        model_trace_json: { stage: 'story_planning', stage_status: 'expert', expert_id: 'story_generator' },
        content_json: { season_question: 'Can she keep the clinic alive?' },
      },
      {
        id: 'outline-1',
        episode_id: 'ep1',
        target_type: 'episode',
        artifact_type: 'episode_outline',
        status: 'approved',
        version: 1,
        content_json: { hook: 'Clinic opens with a crisis.' },
      },
    ]
    mocks.listAITextArtifacts.mockResolvedValue({ data: { ok: true, artifacts: plannedArtifacts } })
    mocks.listAITextArtifacts.mockResolvedValueOnce({ data: { ok: true, artifacts: [] } })
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="generate-story-plan"]').trigger('click')
    await flushPromises()

    expect(mocks.generateSeriesStoryPlan).toHaveBeenCalledWith('sid')
    expect(wrapper.find('[data-test="story-plan-status"]').text()).toContain('故事规划 1/1 集')
    expect(wrapper.find('[data-test="story-plan-status"]').text()).toContain('故事生成专家')
  })

  it('generates an episode script from the expanded episode text panel', async () => {
    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    await wrapper.find('[data-test="episode-text-toggle-ep1"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-test="generate-episode-script-ep1"]').trigger('click')
    await flushPromises()

    expect(mocks.generateEpisodeScript).toHaveBeenCalledWith('sid', 'ep1', { target_duration_seconds: 60 })
    expect(mocks.getSeries).toHaveBeenCalledTimes(2)
    expect(mocks.listAITextArtifacts).toHaveBeenCalled()
  })

  it('uses persisted story-planning status to disable the generate button', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
          story_bible_json: { story_planning: { status: 'running', job_id: 'job-1' } },
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'done', duration_seconds: 5 }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="generate-story-plan"]')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('故事规划中...')
  })

  it('uses completed story-planning status to close the generate action', async () => {
    mocks.getSeries.mockResolvedValueOnce({
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
          story_bible_json: { story_planning: { status: 'completed', job_id: 'job-1' } },
        },
        episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'pending', duration_seconds: 5 }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="generate-story-plan"]')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('故事规划已完成')
    expect(mocks.generateSeriesStoryPlan).not.toHaveBeenCalled()
  })

  it('polls while story planning is active and stops on terminal status', async () => {
    vi.useFakeTimers()
    try {
      mocks.getSeries
        .mockResolvedValueOnce({
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
              story_bible_json: { story_planning: { status: 'running', job_id: 'job-1' } },
            },
            episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'done', duration_seconds: 5 }],
          },
        })
        .mockResolvedValueOnce({
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
              story_bible_json: { story_planning: { status: 'completed', job_id: 'job-1' } },
            },
            episodes: [{ id: 'ep1', episode_number: 1, title: 'Pilot', status: 'done', duration_seconds: 5 }],
          },
        })
      mount(SeriesDetailPage)
      await flushPromises()

      expect(mocks.getSeries).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(5000)
      await flushPromises()
      expect(mocks.getSeries).toHaveBeenCalledTimes(2)
      await vi.advanceTimersByTimeAsync(5000)
      await flushPromises()
      expect(mocks.getSeries).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
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

  it('does not describe an active rendering episode as all episodes completed', async () => {
    mocks.getSeries.mockResolvedValueOnce({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 30,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 30,
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'rendering',
          active_video_run_id: 'run-1',
          video_run_status: 'image_batch_running',
          video_run_stage: 'image_generation',
        }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const buttonText = wrapper.findAll('button').map(btn => btn.text()).join('\n')
    expect(buttonText).toContain('剧集生产中')
    expect(buttonText).not.toContain('全部剧集已完成')
  })

  it('does not describe a draft production run as actively producing', async () => {
    mocks.getSeries.mockResolvedValueOnce({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 30,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 30,
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'rendering',
          active_video_run_id: 'run-1',
          video_run_status: 'draft',
          video_run_stage: 'storyboard_ready',
        }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const buttonText = wrapper.findAll('button').map(btn => btn.text()).join('\n')
    expect(buttonText).toContain('继续生产计划')
    expect(buttonText).not.toContain('剧集生产中')
  })

  it('opens an existing draft production plan instead of stranding the user', async () => {
    mocks.getSeries.mockResolvedValueOnce({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 30,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 30,
        },
        episodes: [{
          id: 'ep1',
          episode_number: 1,
          title: 'Pilot',
          status: 'rendering',
          active_video_run_id: 'run-1',
          video_run_status: 'draft',
          video_run_stage: 'storyboard_ready',
          video_run_route: '/video-production/run-1',
        }],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="start-pipeline"]')
    expect(button.text()).toContain('继续生产计划')
    expect(button.attributes('disabled')).toBeUndefined()

    await button.trigger('click')
    await flushPromises()

    expect(mocks.startEpisodeProduction).not.toHaveBeenCalled()
    expect(mocks.push).toHaveBeenCalledWith('/video-production/run-1')
  })

  it('offers to repair missing episode placeholders instead of stranding a pilot-only series', async () => {
    mocks.getSeries
      .mockResolvedValueOnce({
        data: {
          ok: true,
          series: {
            id: 'sid',
            title: 'City Healer',
            logline: 'One sentence story',
            total_episodes: 30,
            genre: 'drama',
            mode: 'step_by_step',
            target_duration: 30,
          },
          episodes: [{
            id: 'ep1',
            episode_number: 1,
            title: 'Pilot',
            status: 'completed',
          }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          ok: true,
          series: {
            id: 'sid',
            title: 'City Healer',
            logline: 'One sentence story',
            total_episodes: 30,
            genre: 'drama',
            mode: 'step_by_step',
            target_duration: 30,
          },
          episodes: [
            { id: 'ep1', episode_number: 1, title: 'Pilot', status: 'completed' },
            { id: 'ep2', episode_number: 2, title: 'Episode 2', status: 'pending' },
          ],
        },
      })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const button = wrapper.find('[data-test="start-pipeline"]')
    expect(button.text()).toContain('补齐剧集占位')
    expect(button.text()).not.toContain('全部剧集已完成')

    await button.trigger('click')
    await flushPromises()

    expect(mocks.ensureSeriesEpisodes).toHaveBeenCalledWith('sid')
  })

  it('shows the next episode number when placeholders exist', async () => {
    mocks.getSeries.mockResolvedValueOnce({
      data: {
        ok: true,
        series: {
          id: 'sid',
          title: 'City Healer',
          logline: 'One sentence story',
          total_episodes: 30,
          genre: 'drama',
          mode: 'step_by_step',
          target_duration: 30,
        },
        episodes: [
          { id: 'ep1', episode_number: 1, title: 'Pilot', status: 'completed' },
          { id: 'ep2', episode_number: 2, title: 'Episode 2', status: 'pending' },
        ],
      },
    })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    const buttonText = wrapper.findAll('button').map(btn => btn.text()).join('\n')
    expect(buttonText).toContain('生成第 2 集')
    expect(buttonText).not.toContain('全部剧集已完成')
  })

  it('still renders series details when optional pipeline history is unavailable', async () => {
    mocks.listRuns.mockRejectedValue({ response: { status: 404, data: { detail: 'Not Found' } } })

    const wrapper = mount(SeriesDetailPage)
    await flushPromises()

    expect(wrapper.text()).toContain('City Healer')
    expect(wrapper.text()).not.toContain('Request failed with status code 404')
  })
})
