import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  router: { push: vi.fn() },
  listSeries: vi.fn(),
  createSeries: vi.fn(),
  listItems: vi.fn(),
}))

vi.mock('../api/series.js', () => ({
  listSeries: mocks.listSeries,
  createSeries: mocks.createSeries,
}))

vi.mock('../api/referenceData.js', () => ({
  listItems: mocks.listItems,
}))

async function mountPage() {
  const Page = (await import('../views/SeriesListPage.vue')).default
  const wrapper = mount(Page, { global: { mocks: { $router: mocks.router } } })
  await flushPromises()
  return wrapper
}

async function openCreateDialog(wrapper) {
  await wrapper.get('[data-test="open-create-series"]').trigger('click')
  await flushPromises()
}

describe('SeriesListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listSeries.mockResolvedValue({ data: { ok: true, series: [] } })
    mocks.createSeries.mockResolvedValue({ data: { ok: true, series: { id: 'series-1' } } })
    mocks.listItems.mockResolvedValue({
      data: {
        ok: true,
        items: [
          { value: 'drama', label: '剧情' },
          { value: 'health', label: '大健康' },
        ],
      },
    })
  })

  it('shows readable Chinese project creation copy', async () => {
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('系列管理')
    expect(wrapper.text()).toContain('新建系列')
    expect(wrapper.text()).not.toMatch(/绯诲垪|鏂板缓|閫愭|鍏ㄨ嚜|�/)

    await openCreateDialog(wrapper)

    expect(wrapper.text()).toContain('逐步确认模式')
    expect(wrapper.text()).toContain('全自动一键生成')
    expect(wrapper.text()).toContain('Pilot 试点')

    wrapper.unmount()
  })

  it('creates new projects in step-by-step mode by default', async () => {
    const wrapper = await mountPage()

    await openCreateDialog(wrapper)
    await wrapper.get('[data-test="series-create-title"]').setValue('老李控糖')
    await wrapper.get('[data-test="series-create-logline"]').setValue('普通中年人用真实生活方式管理血糖。')
    await wrapper.get('[data-test="submit-create-series"]').trigger('click')
    await flushPromises()

    expect(mocks.createSeries).toHaveBeenCalledWith(expect.objectContaining({
      title: '老李控糖',
      logline: '普通中年人用真实生活方式管理血糖。',
      genre: 'drama',
      total_episodes: 30,
      target_duration: 90,
      mode: 'step_by_step',
      pilot_first: true,
    }))
    expect(mocks.router.push).toHaveBeenCalledWith('/series/series-1')
    expect(mocks.listSeries).toHaveBeenCalledTimes(1)
  })

  it('submits fully automatic mode when the user selects one-click generation', async () => {
    const wrapper = await mountPage()

    await openCreateDialog(wrapper)
    await wrapper.get('[data-test="series-create-title"]').setValue('城市疗愈师')
    await wrapper.get('[data-test="series-create-logline"]').setValue('一位医生用短视频解决城市健康误区。')
    await wrapper.get('[data-test="series-create-mode"]').setValue('fully_automatic')
    await wrapper.get('[data-test="series-create-pilot"]').setChecked(false)
    await wrapper.get('[data-test="submit-create-series"]').trigger('click')
    await flushPromises()

    expect(mocks.createSeries).toHaveBeenCalledWith(expect.objectContaining({
      title: '城市疗愈师',
      logline: '一位医生用短视频解决城市健康误区。',
      mode: 'fully_automatic',
      pilot_first: false,
    }))
    expect(mocks.router.push).toHaveBeenCalledWith('/series/series-1?autostart=production')
  })
})
