import { afterEach, beforeAll, describe, it, expect } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import AssetDetailDrawer from '../components/assets/AssetDetailDrawer.vue'

describe('AssetDetailDrawer', () => {
  beforeAll(() => {
    if (!global.ResizeObserver) {
      global.ResizeObserver = class ResizeObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    }
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders Chinese title and emits close from close button', async () => {
    const wrapper = mount(AssetDetailDrawer, {
      attachTo: document.body,
      props: {
        open: true,
        title: '角色详情',
        subtitle: '林岚',
      },
      slots: {
        default: '<div data-test="drawer-body">内容</div>',
        footer: '<button data-test="drawer-footer">保存</button>',
      },
    })

    await flushPromises()

    expect(document.body.textContent).toContain('角色详情')
    expect(document.body.textContent).toContain('林岚')
    expect(document.querySelector('[data-test="drawer-body"]').textContent).toBe('内容')
    expect(document.querySelector('[data-test="drawer-footer"]').textContent).toBe('保存')

    document.querySelector('[data-test="close-drawer"]').click()
    await flushPromises()

    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('emits close when the backdrop is clicked', async () => {
    const wrapper = mount(AssetDetailDrawer, {
      attachTo: document.body,
      props: {
        open: true,
        title: '场景详情',
      },
    })

    await flushPromises()

    document.querySelector('[data-test="drawer-backdrop"]').click()
    await flushPromises()

    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })

  it('emits close when Escape is pressed', async () => {
    const wrapper = mount(AssetDetailDrawer, {
      attachTo: document.body,
      props: {
        open: true,
        title: '角色详情',
      },
    })

    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    await flushPromises()

    expect(wrapper.emitted('close')).toBeTruthy()
    wrapper.unmount()
  })
})
