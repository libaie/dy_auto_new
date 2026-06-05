import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDelete = vi.fn()

vi.mock('../api/client.js', () => ({
  default: {
    get: (...args) => mockGet(...args),
    post: (...args) => mockPost(...args),
    put: (...args) => mockPut(...args),
    delete: (...args) => mockDelete(...args),
  }
}))

describe('API Clients', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('series API', () => {
    it('listSeries calls GET /series', async () => {
      const { listSeries } = await import('../api/series.js')
      mockGet.mockResolvedValue({ data: { ok: true, series: [] } })
      await listSeries()
      expect(mockGet).toHaveBeenCalledWith('/series', { params: undefined })
    })

    it('createSeries calls POST /series', async () => {
      const { createSeries } = await import('../api/series.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createSeries({ title: 'Test' })
      expect(mockPost).toHaveBeenCalledWith('/series', { title: 'Test' })
    })

    it('getSeries calls GET /series/:id', async () => {
      const { getSeries } = await import('../api/series.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      await getSeries('abc')
      expect(mockGet).toHaveBeenCalledWith('/series/abc')
    })

    it('linkCharacter calls POST with correct path', async () => {
      const { linkCharacter } = await import('../api/series.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await linkCharacter('sid', 'cid')
      expect(mockPost).toHaveBeenCalledWith('/series/sid/characters/cid')
    })

    it('management helpers call update and unlink endpoints', async () => {
      const { updateSeries, unlinkCharacter, unlinkScene } = await import('../api/series.js')
      mockPut.mockResolvedValue({ data: { ok: true } })
      mockDelete.mockResolvedValue({ data: { ok: true } })

      await updateSeries('sid', { title: '新剧集' })
      await unlinkCharacter('sid', 'cid')
      await unlinkScene('sid', 'scene-id')

      expect(mockPut).toHaveBeenCalledWith('/series/sid', { title: '新剧集' })
      expect(mockDelete).toHaveBeenCalledWith('/series/sid/characters/cid')
      expect(mockDelete).toHaveBeenCalledWith('/series/sid/scenes/scene-id')
    })

    it('getAgencyConsole calls the agency console endpoint', async () => {
      const { getAgencyConsole } = await import('../api/series.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      await getAgencyConsole('sid')
      expect(mockGet).toHaveBeenCalledWith('/series/sid/agency-console')
    })

    it('style lock helpers call the style-lock endpoints', async () => {
      const { getStyleLock, lockSeriesStyle } = await import('../api/series.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      mockPost.mockResolvedValue({ data: { ok: true } })
      await getStyleLock('sid')
      await lockSeriesStyle('sid')
      expect(mockGet).toHaveBeenCalledWith('/series/sid/style-lock')
      expect(mockPost).toHaveBeenCalledWith('/series/sid/style-lock', undefined, { timeout: 600000 })
    })
  })

  describe('characters API', () => {
    it('listCharacters calls GET /characters', async () => {
      const { listCharacters } = await import('../api/characters.js')
      mockGet.mockResolvedValue({ data: { ok: true, characters: [] } })
      await listCharacters()
      expect(mockGet).toHaveBeenCalledWith('/characters', { params: undefined })
    })

    it('listCharacters forwards query params', async () => {
      const { listCharacters } = await import('../api/characters.js')
      mockGet.mockResolvedValue({ data: { ok: true, characters: [] } })
      await listCharacters({ include_archived: true })
      expect(mockGet).toHaveBeenCalledWith('/characters', { params: { include_archived: true } })
    })

    it('createCharacter calls POST /characters', async () => {
      const { createCharacter } = await import('../api/characters.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createCharacter({ name: 'Hero' })
      expect(mockPost).toHaveBeenCalledWith('/characters', { name: 'Hero' })
    })

    it('asset management helpers call AI rewrite candidate and reference generation endpoints', async () => {
      const { aiRewriteCharacter, generateCharacterReferences } = await import('../api/characters.js')
      mockPost.mockResolvedValue({ data: { ok: true } })

      await aiRewriteCharacter('char-1')
      await generateCharacterReferences('char-1', { slot: 'avatar_front_url' })

      expect(mockPost).toHaveBeenCalledWith('/characters/char-1/ai-rewrite-candidate', {})
      expect(mockPost).toHaveBeenCalledWith('/characters/char-1/reference-images/generate', { slot: 'avatar_front_url' })
    })
  })

  describe('scenes API', () => {
    it('listScenes forwards query params', async () => {
      const { listScenes } = await import('../api/scenes.js')
      mockGet.mockResolvedValue({ data: { ok: true, scenes: [] } })
      await listScenes({ include_archived: true })
      expect(mockGet).toHaveBeenCalledWith('/scenes', { params: { include_archived: true } })
    })

    it('asset management helpers call AI rewrite candidate and reference generation endpoints', async () => {
      const { aiRewriteScene, generateSceneReferences } = await import('../api/scenes.js')
      mockPost.mockResolvedValue({ data: { ok: true } })

      await aiRewriteScene('scene-1', { instruction: '强化空间感' })
      await generateSceneReferences('scene-1')

      expect(mockPost).toHaveBeenCalledWith('/scenes/scene-1/ai-rewrite-candidate', { instruction: '强化空间感' })
      expect(mockPost).toHaveBeenCalledWith('/scenes/scene-1/reference-images/generate', {})
    })
  })

  describe('pipeline API', () => {
    it('startPipeline calls POST with body payload', async () => {
      const { startPipeline } = await import('../api/pipeline.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await startPipeline('sid', 'eid', 'step_by_step', { imageModel: 'img-id' }, null)
      expect(mockPost).toHaveBeenCalledWith('/pipeline/start', {
        series_id: 'sid', episode_id: 'eid', mode: 'step_by_step',
        model_ids: { imageModel: 'img-id' }, director_plan: null,
      })
    })

    it('getRun calls GET with correct path', async () => {
      const { getRun } = await import('../api/pipeline.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      await getRun('sid', 'rid')
      expect(mockGet).toHaveBeenCalledWith('/pipeline/runs/sid/rid')
    })

    it('getRunById calls GET run-id lookup path', async () => {
      const { getRunById } = await import('../api/pipeline.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      await getRunById('rid')
      expect(mockGet).toHaveBeenCalledWith('/pipeline/runs/by-id/rid')
    })
  })

  describe('director API', () => {
    it('autoPlanEpisode calls POST /director/auto-plan', async () => {
      const { autoPlanEpisode } = await import('../api/director.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await autoPlanEpisode('sid', 'eid', 60)
      expect(mockPost).toHaveBeenCalledWith('/director/auto-plan', {
        series_id: 'sid',
        episode_id: 'eid',
        target_duration: 60,
      })
    })

    it('episode plan helpers call director control-plane endpoints', async () => {
      const { createEpisodePlan, createShotSegments } = await import('../api/director.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createEpisodePlan({ series_id: 'sid', episode_id: 'eid', include_segments: false })
      await createShotSegments({ production_shot_id: 'shot-1' })
      expect(mockPost).toHaveBeenCalledWith('/director/episode-plan', {
        series_id: 'sid',
        episode_id: 'eid',
        include_segments: false,
      })
      expect(mockPost).toHaveBeenCalledWith('/director/shot-segments', {
        production_shot_id: 'shot-1',
      })
    })
  })

  describe('aiConfig API', () => {
    it('listModels calls GET /ai-models', async () => {
      const { listModels } = await import('../api/aiConfig.js')
      mockGet.mockResolvedValue({ data: { ok: true, models: [] } })
      await listModels({ model_type: 'llm' })
      expect(mockGet).toHaveBeenCalledWith('/ai-models', { params: { model_type: 'llm' } })
    })

    it('getModelOptions calls GET /ai-models/options', async () => {
      const { getModelOptions } = await import('../api/aiConfig.js')
      mockGet.mockResolvedValue({ data: { ok: true, options: [] } })
      await getModelOptions('llm')
      expect(mockGet).toHaveBeenCalledWith('/ai-models/options', { params: { model_type: 'llm' } })
    })

    it('createModel calls POST /ai-models', async () => {
      const { createModel } = await import('../api/aiConfig.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createModel({ name: 'Test', model_type: 'llm', provider: 'deepseek' })
      expect(mockPost).toHaveBeenCalledWith('/ai-models', { name: 'Test', model_type: 'llm', provider: 'deepseek' })
    })

    it('testModelConnection calls POST /ai-models/:id/test', async () => {
      const { testModelConnection } = await import('../api/aiConfig.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await testModelConnection('uuid-123')
      expect(mockPost).toHaveBeenCalledWith('/ai-models/uuid-123/test')
    })
  })

  describe('video production API', () => {
    it('createVideoProductionRun calls POST /video-production/runs', async () => {
      const { createVideoProductionRun } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createVideoProductionRun('sid', 'eid')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs', {
        series_id: 'sid',
        episode_id: 'eid',
      })
    })

    it('startEpisodeProduction calls POST /video-production/runs/start', async () => {
      const { startEpisodeProduction } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await startEpisodeProduction({ series_id: 'sid', episode_id: 'eid', target_duration_seconds: 60 })
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/start', {
        series_id: 'sid',
        episode_id: 'eid',
        target_duration_seconds: 60,
        budget_limit: 1,
        autostart_images: true,
        run_type: 'real_short_e2e',
      })
    })

    it('createOneSentenceVideo calls POST /video-production/one-sentence', async () => {
      const { createOneSentenceVideo } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createOneSentenceVideo({
        prompt: 'one sentence story',
        target_duration_seconds: 60,
        autostart_images: false,
      })
      expect(mockPost).toHaveBeenCalledWith('/video-production/one-sentence', {
        prompt: 'one sentence story',
        title: undefined,
        genre: undefined,
        target_duration_seconds: 60,
        budget_limit: 1,
        autostart_images: false,
        run_type: 'real_short_e2e',
      })
    })

    it('listReviewItems calls GET with filters', async () => {
      const { listReviewItems } = await import('../api/videoProduction.js')
      mockGet.mockResolvedValue({ data: { ok: true, items: [] } })
      await listReviewItems({ run_id: 'rid', statuses: 'review_pending,regenerating' })
      expect(mockGet).toHaveBeenCalledWith('/video-production/review-items', {
        params: { run_id: 'rid', statuses: 'review_pending,regenerating' },
      })
    })

    it('reviewAsset calls POST asset review endpoint', async () => {
      const { reviewAsset } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await reviewAsset('aid', 'approve', 'ok')
      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/aid/review', {
        action: 'approve',
        comment: 'ok',
      })
    })

    it('review management helpers call void and image-edit endpoints', async () => {
      const { voidProductionAsset, imageEditProductionAsset } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })

      await voidProductionAsset('asset-1')
      await imageEditProductionAsset('asset-1', { instruction: '去掉杂物' })

      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/asset-1/void', {})
      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/asset-1/image-edit', { instruction: '去掉杂物' })
    })

    it('video stage helpers call the video endpoints', async () => {
      const { startVideoStage, syncVideoStage } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await startVideoStage('rid')
      await syncVideoStage('rid')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/rid/start-videos')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/rid/sync-video-results')
    })

    it('compose helpers call the compose endpoints', async () => {
      const { startComposeStage, syncComposeStage } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await startComposeStage('rid')
      await syncComposeStage('rid')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/rid/compose')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/rid/sync-compose-results')
    })

    it('regeneration helpers call the regeneration endpoints', async () => {
      const { startAssetRegeneration, syncAssetRegeneration } = await import('../api/videoProduction.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await startAssetRegeneration('aid')
      await syncAssetRegeneration('aid')
      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/aid/start-regeneration')
      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/aid/sync-regeneration')
    })

    it('production control helpers call tree, retry, bulk review, and collection endpoints', async () => {
      const {
        getProductionTree,
        getRunProductionTree,
        getSegmentDetail,
        getSegmentRetryImpact,
        getRunCosts,
        retryProductionSegment,
        bulkReviewProductionAssets,
        createVideoCollection,
        pauseProductionRun,
        resumeProductionRun,
        runRealWorkerStep,
        retryAssetPersistence,
        getProviderStageTasks,
      } = await import('../api/videoProduction.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      mockPost.mockResolvedValue({ data: { ok: true } })

      await getProductionTree('plan-1', { page: 2, status: 'failed' })
      await getRunProductionTree('run-1', { page: 1 })
      await getSegmentDetail('seg-1', { history_limit: 10 })
      await getSegmentRetryImpact('seg-1')
      await getRunCosts('run-1')
      await retryProductionSegment('seg-1')
      await bulkReviewProductionAssets({ asset_ids: ['a1'], action: 'approve', comment: 'ok' })
      await createVideoCollection('series-1')
      await pauseProductionRun('run-1')
      await resumeProductionRun('run-1')
      await runRealWorkerStep('run-1')
      await retryAssetPersistence('asset-1')
      await getProviderStageTasks('run-1', { page: 2 })

      expect(mockGet).toHaveBeenCalledWith('/video-production/plans/plan-1/tree', {
        params: { page: 2, page_size: 50, status: 'failed' },
      })
      expect(mockGet).toHaveBeenCalledWith('/video-production/runs/run-1/tree', {
        params: { page: 1, page_size: 50 },
      })
      expect(mockGet).toHaveBeenCalledWith('/video-production/segments/seg-1/detail', {
        params: { history_limit: 10 },
      })
      expect(mockGet).toHaveBeenCalledWith('/video-production/runs/run-1/provider-stage-tasks', {
        params: { page: 2, page_size: 50 },
      })
      expect(mockGet).toHaveBeenCalledWith('/video-production/segments/seg-1/retry-impact')
      expect(mockGet).toHaveBeenCalledWith('/video-production/runs/run-1/costs')
      expect(mockPost).toHaveBeenCalledWith('/video-production/segments/seg-1/retry')
      expect(mockPost).toHaveBeenCalledWith('/video-production/reviews/bulk-action', {
        asset_ids: ['a1'],
        action: 'approve',
        comment: 'ok',
      })
      expect(mockPost).toHaveBeenCalledWith('/video-production/collections', { series_id: 'series-1' })
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/pause')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/resume')
      expect(mockPost).toHaveBeenCalledWith('/video-production/runs/run-1/worker-step', {
        lease_id: 'ui-real-worker',
        batch_size: 1,
      })
      expect(mockPost).toHaveBeenCalledWith('/video-production/assets/asset-1/persist-retry')
    })
  })
})
