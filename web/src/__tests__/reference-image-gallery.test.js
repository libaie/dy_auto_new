import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

import ReferenceImageGallery from '../components/assets/ReferenceImageGallery.vue'

describe('ReferenceImageGallery', () => {
  beforeEach(() => {
    vi.useRealTimers()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn(() => Promise.resolve()),
      },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows Chinese empty state and emits regenerate for one slot', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          { key: 'avatar_front_url', label: '正面', url: '' },
        ],
        loadingSlot: '',
      },
    })

    expect(wrapper.text()).toContain('待生成')
    expect(wrapper.find('label[for="reference-url-avatar_front_url"]').text()).toContain('正面链接')

    await wrapper.find('[data-test="regenerate-avatar_front_url"]').trigger('click')

    expect(wrapper.emitted('regenerate')[0]).toEqual(['avatar_front_url'])
  })

  it('emits regenerate all with each slot key', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          { key: 'avatar_front_url', label: '正面', url: '' },
          { key: 'avatar_side_url', label: '侧面', url: '' },
        ],
        loadingSlot: '',
      },
    })

    await wrapper.find('[data-test="regenerate-all"]').trigger('click')

    expect(wrapper.emitted('regenerate')).toEqual([
      ['avatar_front_url'],
      ['avatar_side_url'],
    ])
  })

  it('shows preview, copies URL, and emits replace-url with typed URL', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '场景参考图',
        slots: [
          { key: 'reference_wideshot_url', label: '广角', url: 'https://old.test/a.png' },
        ],
        loadingSlot: '',
      },
    })

    expect(wrapper.find('img[alt="广角参考图"]').exists()).toBe(true)

    await wrapper.find('[data-test="copy-reference_wideshot_url"]').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('https://old.test/a.png')

    await wrapper.find('[data-test="edit-reference_wideshot_url"]').trigger('click')
    await wrapper.find('[data-test="url-input-reference_wideshot_url"]').setValue('https://new.test/a.png')
    await wrapper.find('[data-test="save-url-reference_wideshot_url"]').trigger('click')

    expect(wrapper.emitted('replace-url')[0]).toEqual(['reference_wideshot_url', 'https://new.test/a.png'])
  })

  it('opens the original image preview and normalizes managed static URLs', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          {
            key: 'avatar_front_url',
            label: '正面',
            url: 'http://127.0.0.1:8000/static/image-creation/outputs/front.png',
          },
        ],
        loadingSlot: '',
      },
    })

    const preview = wrapper.find('[data-test="preview-image-avatar_front_url"]')
    expect(preview.attributes('src')).toBe('/static/image-creation/outputs/front.png')

    await wrapper.find('[data-test="open-original-avatar_front_url"]').trigger('click')

    expect(wrapper.find('[data-test="reference-original-modal"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="reference-original-image"]').attributes('src')).toBe('/static/image-creation/outputs/front.png')
  })

  it('marks expired provider signed URLs as unavailable instead of showing a broken image', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-02T00:00:00Z'))
    const expiredUrl = 'https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/doubao-seedream-5-0/ref.jpeg?X-Tos-Date=20260528T061838Z&X-Tos-Expires=86400'

    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          { key: 'avatar_front_url', label: '正面', url: expiredUrl },
        ],
        loadingSlot: '',
      },
    })

    expect(wrapper.find('[data-test="preview-image-avatar_front_url"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('链接已过期')
    expect(wrapper.find('[data-test="regenerate-avatar_front_url"]').exists()).toBe(true)
  })

  it('does not render unsupported URL protocols as preview images', () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          { key: 'avatar_front_url', label: '正面', url: 'javascript:alert(1)' },
        ],
        loadingSlot: '',
      },
    })

    expect(wrapper.find('[data-test="preview-image-avatar_front_url"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="open-original-avatar_front_url"]').exists()).toBe(false)
  })

  it('clears an in-progress URL edit when slots change', async () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          { key: 'avatar_front_url', label: '正面', url: 'https://old.test/a.png' },
        ],
        loadingSlot: '',
      },
    })

    await wrapper.find('[data-test="edit-avatar_front_url"]').trigger('click')
    await wrapper.find('[data-test="url-input-avatar_front_url"]').setValue('https://draft.test/a.png')

    await wrapper.setProps({
      slots: [
        { key: 'avatar_front_url', label: '正面', url: 'https://new-asset.test/a.png' },
      ],
    })

    expect(wrapper.find('[data-test="url-input-avatar_front_url"]').element.value).toBe('https://new-asset.test/a.png')
    expect(wrapper.find('[data-test="save-url-avatar_front_url"]').exists()).toBe(false)
  })

  it('shows style lock reference generation progress per slot', () => {
    const wrapper = mount(ReferenceImageGallery, {
      props: {
        title: '角色参考图',
        slots: [
          {
            key: 'avatar_front_url',
            label: '正面',
            url: '',
            progress: {
              status: 'generating',
              source: 'style_lock',
              error: '',
            },
          },
          {
            key: 'avatar_side_url',
            label: '侧面',
            url: '',
            progress: {
              status: 'failed',
              source: 'style_lock',
              error: 'provider timeout',
            },
          },
        ],
        loadingSlot: '',
      },
    })

    expect(wrapper.find('[data-test="progress-avatar_front_url"]').text()).toContain('风格锁定生成中')
    expect(wrapper.find('[data-test="progress-avatar_side_url"]').text()).toContain('生成失败')
    expect(wrapper.text()).toContain('provider timeout')
  })
})
