import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()

vi.mock('../api/client.js', () => ({
  default: {
    get: (...args) => mockGet(...args),
    post: (...args) => mockPost(...args),
  },
}))

describe('image creation API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('createImageTask posts to /image-creation/tasks', async () => {
    const { createImageTask } = await import('../api/imageCreation.js')
    const payload = { mode: 'text_to_image', prompt: '一只蓝色机器人', count: 2 }

    await createImageTask(payload)

    expect(mockPost).toHaveBeenCalledWith('/image-creation/tasks', payload)
  })

  it('listImageAssets gets /image-creation/assets with params', async () => {
    const { listImageAssets } = await import('../api/imageCreation.js')
    const params = { task_id: 'task-1', status: 'pending' }

    await listImageAssets(params)

    expect(mockGet).toHaveBeenCalledWith('/image-creation/assets', { params })
  })

  it('covers upload, task lookup, sync, review, and edit endpoints', async () => {
    const {
      uploadImageSource,
      getImageTask,
      syncImageTask,
      reviewImageAsset,
      editImageAsset,
    } = await import('../api/imageCreation.js')
    const formData = new FormData()
    const reviewPayload = { action: 'approve', comment: '可用' }
    const editPayload = { prompt: '加强光影' }

    await uploadImageSource(formData)
    await getImageTask('task-1')
    await syncImageTask('task-1')
    await reviewImageAsset('asset-1', reviewPayload)
    await editImageAsset('asset-1', editPayload)

    expect(mockPost).toHaveBeenCalledWith('/image-creation/uploads', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    expect(mockGet).toHaveBeenCalledWith('/image-creation/tasks/task-1')
    expect(mockPost).toHaveBeenCalledWith('/image-creation/tasks/task-1/sync')
    expect(mockPost).toHaveBeenCalledWith('/image-creation/assets/asset-1/review', reviewPayload)
    expect(mockPost).toHaveBeenCalledWith('/image-creation/assets/asset-1/edit', editPayload)
  })
})
