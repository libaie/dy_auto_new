import { beforeEach, describe, expect, it, vi } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('../api/client.js', () => ({
  default: {
    get: (...args) => mockGet(...args),
    post: (...args) => mockPost(...args),
  },
}))

describe('video production run type API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('passes run_type for one-sentence video creation', async () => {
    const { createOneSentenceVideo } = await import('../api/videoProduction.js')

    await createOneSentenceVideo({
      prompt: 'one sentence story',
      run_type: 'mock_series_scale',
    })

    expect(mockPost).toHaveBeenCalledWith('/video-production/one-sentence', {
      prompt: 'one sentence story',
      title: undefined,
      genre: undefined,
      target_duration_seconds: 60,
      budget_limit: undefined,
      autostart_images: true,
      run_type: 'mock_series_scale',
    })
  })

  it('defaults one-sentence run_type to real_short_e2e', async () => {
    const { createOneSentenceVideo } = await import('../api/videoProduction.js')

    await createOneSentenceVideo({
      prompt: 'one sentence story',
    })

    expect(mockPost).toHaveBeenCalledWith('/video-production/one-sentence', {
      prompt: 'one sentence story',
      title: undefined,
      genre: undefined,
      target_duration_seconds: 60,
      budget_limit: 1,
      autostart_images: true,
      run_type: 'real_short_e2e',
    })
  })

  it('passes run_type for linked episode start', async () => {
    const { startEpisodeProduction } = await import('../api/videoProduction.js')

    await startEpisodeProduction({
      series_id: 'series-1',
      episode_id: 'episode-1',
      target_duration_seconds: 90,
      run_type: 'mock_series_scale',
    })

    expect(mockPost).toHaveBeenCalledWith('/video-production/runs/start', {
      series_id: 'series-1',
      episode_id: 'episode-1',
      target_duration_seconds: 90,
      budget_limit: undefined,
      autostart_images: true,
      run_type: 'mock_series_scale',
    })
  })

  it('defaults linked episode run_type to real_short_e2e', async () => {
    const { startEpisodeProduction } = await import('../api/videoProduction.js')

    await startEpisodeProduction({
      series_id: 'series-1',
      episode_id: 'episode-1',
      target_duration_seconds: 90,
    })

    expect(mockPost).toHaveBeenCalledWith('/video-production/runs/start', {
      series_id: 'series-1',
      episode_id: 'episode-1',
      target_duration_seconds: 90,
      budget_limit: 1,
      autostart_images: true,
      run_type: 'real_short_e2e',
    })
  })

  it('gets run readiness', async () => {
    const { getRunReadiness } = await import('../api/videoProduction.js')

    await getRunReadiness('run-1')

    expect(mockGet).toHaveBeenCalledWith('/video-production/runs/run-1/readiness')
  })

  it('posts mock worker step with defaults', async () => {
    const { runMockSchedulerStep } = await import('../api/videoProduction.js')

    await runMockSchedulerStep('run-1')

    expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/mock-worker-step', {
      lease_id: 'ui-worker',
      batch_size: 1,
    })
  })
})
