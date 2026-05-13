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
  })

  describe('characters API', () => {
    it('listCharacters calls GET /characters', async () => {
      const { listCharacters } = await import('../api/characters.js')
      mockGet.mockResolvedValue({ data: { ok: true, characters: [] } })
      await listCharacters()
      expect(mockGet).toHaveBeenCalledWith('/characters')
    })

    it('createCharacter calls POST /characters', async () => {
      const { createCharacter } = await import('../api/characters.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await createCharacter({ name: 'Hero' })
      expect(mockPost).toHaveBeenCalledWith('/characters', { name: 'Hero' })
    })
  })

  describe('pipeline API', () => {
    it('startPipeline calls POST with params', async () => {
      const { startPipeline } = await import('../api/pipeline.js')
      mockPost.mockResolvedValue({ data: { ok: true } })
      await startPipeline('sid', 'eid', 'step_by_step')
      expect(mockPost).toHaveBeenCalledWith('/pipeline/start', null, {
        params: { series_id: 'sid', episode_id: 'eid', mode: 'step_by_step' }
      })
    })

    it('getRun calls GET with correct path', async () => {
      const { getRun } = await import('../api/pipeline.js')
      mockGet.mockResolvedValue({ data: { ok: true } })
      await getRun('sid', 'rid')
      expect(mockGet).toHaveBeenCalledWith('/pipeline/runs/sid/rid')
    })
  })

  describe('aiConfig API', () => {
    it('updateModels calls PUT /ai-config/models', async () => {
      const { updateModels } = await import('../api/aiConfig.js')
      mockPut.mockResolvedValue({ data: { ok: true } })
      await updateModels({ llm_provider: 'deepseek' })
      expect(mockPut).toHaveBeenCalledWith('/ai-config/models', { llm_provider: 'deepseek' })
    })
  })
})
