import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { params: { seriesId: 'series-1' } },
  createVideoCollection: vi.fn(() => Promise.resolve({ data: { ok: true, collection: { id: 'col-1', status: 'draft', included_episode_ids: ['ep-1'], duration_seconds: 60 } } })),
}))

vi.mock('vue-router', () => ({ useRoute: () => mocks.route }))
vi.mock('../api/videoProduction.js', () => ({ createVideoCollection: mocks.createVideoCollection }))

describe('CollectionBuilderPage', () => {
  it('creates a collection from approved episodes', async () => {
    const Page = (await import('../views/CollectionBuilderPage.vue')).default
    const wrapper = mount(Page)

    await wrapper.find('button[data-test="create-collection"]').trigger('click')
    await flushPromises()

    expect(mocks.createVideoCollection).toHaveBeenCalledWith('series-1')
    expect(wrapper.text()).toContain('col-1')
    expect(wrapper.text()).toContain('60')
  })
})
