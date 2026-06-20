import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const pixelleMocks = vi.hoisted(() => ({
  generateVideoAsync: vi.fn(),
  getTask: vi.fn(),
  uploadFile: vi.fn(),
}))

vi.mock('../api/pixelle-client.js', () => ({
  generateVideoAsync: pixelleMocks.generateVideoAsync,
  getTask: pixelleMocks.getTask,
  uploadFile: pixelleMocks.uploadFile,
  getVideoFileUrl: (videoPath) => videoPath ? `/api/pixelle-proxy/api/files/${encodeURIComponent(videoPath)}` : '',
}))

import ActionTransferPanel from '../components/video-studio/ActionTransferPanel.vue'
import CustomMediaPanel from '../components/video-studio/CustomMediaPanel.vue'
import DigitalHumanPanel from '../components/video-studio/DigitalHumanPanel.vue'
import ImageToVideoPanel from '../components/video-studio/ImageToVideoPanel.vue'

function file(name, type = 'image/png') {
  return new File(['content'], name, { type })
}

async function setFiles(wrapper, files, inputIndex = 0) {
  const input = wrapper.findAll('input[type="file"]')[inputIndex]
  Object.defineProperty(input.element, 'files', { value: files, configurable: true })
  await input.trigger('change')
}

async function clickGenerateAndFinish(wrapper) {
  await wrapper.find('button').trigger('click')
  await flushPromises()
  await vi.advanceTimersByTimeAsync(5000)
  await flushPromises()
}

function setupPixelleTask(uploadPaths) {
  uploadPaths.forEach((path) => {
    pixelleMocks.uploadFile.mockResolvedValueOnce({ data: { path } })
  })
  pixelleMocks.generateVideoAsync.mockResolvedValue({ data: { task_id: 'task-1' } })
  pixelleMocks.getTask.mockResolvedValue({
    data: {
      status: 'completed',
      video_path: 'output/final.mp4',
      duration: 5,
      file_size: 12345,
    },
  })
}

function renderedResultVideo(wrapper) {
  const videos = wrapper.findAll('video')
  return videos[videos.length - 1]
}

describe('video studio business closure', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    global.URL.createObjectURL = vi.fn((value) => `blob:${value.name}`)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('custom media uploads selected assets before generation and exposes the finished video', async () => {
    setupPixelleTask(['uploads/source.png', 'uploads/source.mp4'])
    const wrapper = mount(CustomMediaPanel)

    await setFiles(wrapper, [
      file('source.png'),
      file('source.mp4', 'video/mp4'),
    ])
    await clickGenerateAndFinish(wrapper)

    expect(pixelleMocks.uploadFile).toHaveBeenCalledTimes(2)
    expect(pixelleMocks.uploadFile.mock.invocationCallOrder[0])
      .toBeLessThan(pixelleMocks.generateVideoAsync.mock.invocationCallOrder[0])
    const payload = pixelleMocks.generateVideoAsync.mock.calls[0][0]
    expect(payload.asset_paths).toEqual(['uploads/source.png', 'uploads/source.mp4'])
    expect(payload.media_paths).toEqual(['uploads/source.png', 'uploads/source.mp4'])
    expect(renderedResultVideo(wrapper).attributes('src')).toBe('/api/pixelle-proxy/api/files/output%2Ffinal.mp4')
    expect(wrapper.find('a[download]').attributes('href')).toBe('/api/pixelle-proxy/api/files/output%2Ffinal.mp4')
  })

  it('digital human uploads character and goods files into the generation payload', async () => {
    setupPixelleTask(['uploads/host.png', 'uploads/goods.png'])
    const wrapper = mount(DigitalHumanPanel)

    await setFiles(wrapper, [file('host.png')], 0)
    await setFiles(wrapper, [file('goods.png')], 1)
    await clickGenerateAndFinish(wrapper)

    const payload = pixelleMocks.generateVideoAsync.mock.calls[0][0]
    expect(payload.character_paths).toEqual(['uploads/host.png'])
    expect(payload.goods_paths).toEqual(['uploads/goods.png'])
    expect(renderedResultVideo(wrapper).attributes('src')).toBe('/api/pixelle-proxy/api/files/output%2Ffinal.mp4')
  })

  it('image-to-video uploads reference media and sends the requested duration', async () => {
    setupPixelleTask(['uploads/reference.png'])
    const wrapper = mount(ImageToVideoPanel)

    await setFiles(wrapper, [file('reference.png')])
    await wrapper.find('input[type="range"]').setValue(9)
    await clickGenerateAndFinish(wrapper)

    const payload = pixelleMocks.generateVideoAsync.mock.calls[0][0]
    expect(payload.image_paths).toEqual(['uploads/reference.png'])
    expect(payload.duration).toBe(9)
    expect(renderedResultVideo(wrapper).attributes('src')).toBe('/api/pixelle-proxy/api/files/output%2Ffinal.mp4')
  })

  it('action transfer uploads the source video and sends it as the source path', async () => {
    setupPixelleTask(['uploads/action.mp4'])
    const wrapper = mount(ActionTransferPanel)

    await setFiles(wrapper, [file('action.mp4', 'video/mp4')])
    await clickGenerateAndFinish(wrapper)

    const payload = pixelleMocks.generateVideoAsync.mock.calls[0][0]
    expect(payload.source_video_path).toBe('uploads/action.mp4')
    expect(renderedResultVideo(wrapper).attributes('src')).toBe('/api/pixelle-proxy/api/files/output%2Ffinal.mp4')
  })
})
