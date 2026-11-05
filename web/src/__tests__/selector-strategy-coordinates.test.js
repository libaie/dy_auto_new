// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
import { mount, shallowMount, flushPromises } from '@vue/test-utils'
import StrategyCard from '../components/StrategyCard.vue'
import SelectorsPage from '../views/SelectorsPage.vue'
const api = vi.hoisted(() => ({
  listSelectors: vi.fn().mockResolvedValue({ data: { selectors: [] } }),
  createSelector: vi.fn().mockResolvedValue({ data: {} }),
  updateSelector: vi.fn().mockResolvedValue({ data: {} }),
  deleteSelector: vi.fn(), toggleSelector: vi.fn(), generateRegex: vi.fn(), generateCleanPrompt: vi.fn(),
}))
vi.mock('../api/selectors.js', () => api)
vi.mock('../stores/toast.js', () => ({ useToastStore: () => ({ error: vi.fn(), success: vi.fn() }) }))
vi.mock('../composables/useWebSocket.js', () => ({ useWebSocket: () => ({}) }))

function card(strategy, purpose = 'locate') {
  const wrapper = mount(StrategyCard, {
    props: { strategy, purpose, index: 0, totalCount: 1 },
    attrs: { onUpdate: next => wrapper.setProps({ strategy: next }) },
  })
  return wrapper
}
const last = w => w.emitted('update').at(-1)[0]

describe('strategy geometry editor', () => {
  it('keeps loaded legacy screen ratios and zero values until explicitly changed', async () => {
    const w = card({ type: 'coordinate', x_percent: 0, y_percent: 1, custom: 'keep' })
    expect(w.text()).toContain('屏幕比例')
    expect(w.find('[data-testid="position-space"]').element.value).toBe('legacy')
    await w.find('[data-testid="legacy-x"]').setValue('0')
    expect(last(w)).toEqual({ type: 'coordinate', x_percent: 0, y_percent: 1, custom: 'keep' })
    await w.find('[data-testid="position-space"]').setValue('content_normalized')
    expect(last(w)).toEqual({ type: 'coordinate', position: { space: 'content_normalized', x: 0, y: 1 }, custom: 'keep' })
  })
  it('defaults a new coordinate to explicit content position without leaking legacy node offsets', async () => {
    const w = card({ type: 'text', value: 'send', x_percent: 150, y_percent: -20 })
    await w.find('select').setValue('coordinate')
    expect(last(w)).toEqual({ type: 'coordinate', position: { space: 'content_normalized', x: 0.5, y: 0.5 } })
    await w.find('select').setValue('text')
    expect(last(w)).toEqual({ type: 'text', value: '' })
  })
  it('keeps priority and extension fields when switching types while clearing type-specific geometry', async () => {
    const w = card({ type: 'coordinate', x_percent: 0, y_percent: 1, priority: 2, custom: { keep: true } })
    await w.find('select').setValue('text')
    expect(last(w)).toEqual({ type: 'text', value: '', priority: 2, custom: { keep: true } })
  })
  it('labels legacy image offsets as pixels and node offsets as target percentages', async () => {
    const image = card({ type: 'image', template: 'a.png', x_percent: 0, y_percent: 12 })
    await image.find('[data-testid="legacy-offset-toggle"]').trigger('click')
    expect(image.text()).toContain('像素')
    expect(image.find('[data-testid="legacy-offset-x"]').element.value).toBe('0')
    const node = card({ type: 'text', value: 'send', x_percent: 0 })
    await node.find('[data-testid="legacy-offset-toggle"]').trigger('click')
    expect(node.text()).toContain('控件宽高百分比')
  })
  it('emits explicit zero offsets and region with anchor controls preserving unrelated fields', async () => {
    const w = card({ type: 'text', value: 'send', custom: { keep: true } })
    await w.find('[data-testid="offset-unit"]').setValue('dp')
    await w.find('[data-testid="offset-x"]').setValue('0')
    expect(last(w).offset).toEqual({ unit: 'dp', x: 0, y: 0 })
    await w.find('[data-testid="region-space"]').setValue('anchor_normalized')
    await w.find('[data-testid="region-left"]').setValue('0')
    await w.find('[data-testid="anchor-type"]').setValue('id')
    await w.find('[data-testid="anchor-value"]').setValue('container')
    expect(last(w).region).toEqual({ space: 'anchor_normalized', left: 0, top: 0, right: 1, bottom: 1 })
    expect(last(w).anchor).toEqual({ type: 'id', value: 'container' })
    expect(last(w).custom).toEqual({ keep: true })
  })
  it('removes explicit offsets without rewriting legacy offsets or unrelated conditions', async () => {
    const strategy = { conditions: [{ type: 'id', value: 'send' }], logic: 'and', x_percent: 0, y_percent: 150, offset: { unit: 'px', x: 0, y: 8 }, custom: 'keep' }
    const w = card(strategy)
    await w.find('[data-testid="offset-unit"]').setValue('')
    const { offset, ...legacy } = strategy
    expect(last(w)).toEqual(legacy)
  })
  it('edits image scale metadata without altering threshold', async () => {
    const w = card({ type: 'image', template: 'a.png', threshold: 0 })
    await w.find('[data-testid="source-resolution"]').setValue('1080x2400')
    await w.find('[data-testid="source-density"]').setValue('3')
    await w.find('[data-testid="template-scales"]').setValue('0.9, 1, 1.1')
    expect(last(w)).toMatchObject({ source_resolution: '1080x2400', source_density: 3, scales: [0.9, 1, 1.1], threshold: 0 })
    expect(w.text()).toContain('0.00')
    expect(w.find('input[type=range]').element.value).toBe('0')
  })
})


describe('selector page geometry persistence', () => {
  it('saves a loaded legacy zero coordinate without introducing new fields', async () => {
    const w = shallowMount(SelectorsPage)
    await flushPromises()
    const strategies = [{ type: 'coordinate', x_percent: 0, y_percent: 1, custom: 'keep' }]
    w.vm.openEditDialog({ action_name: 'edge', strategies, platform_version: 'default', resolution_profile: '720x1600' })
    await w.vm.handleSave()
    expect(api.updateSelector).toHaveBeenLastCalledWith('edge', expect.objectContaining({ strategies }))
    w.unmount()
  })
  it('rejects coordinate evidence nested in page detection conditions before submitting', async () => {
    api.createSelector.mockClear()
    const w = shallowMount(SelectorsPage)
    await flushPromises()
    w.vm.openCreateDialog()
    w.vm.form.action_name = 'page_ready'
    w.vm.form.purpose = 'page_detect'
    w.vm.form.strategies = JSON.stringify([{ conditions: [{ type: 'coordinate', x_percent: 0, y_percent: 0 }] }])
    await w.vm.handleSave()
    expect(w.vm.formError).toContain('页面检测不能使用坐标')
    expect(api.createSelector).not.toHaveBeenCalled()
    w.unmount()
  })
})
