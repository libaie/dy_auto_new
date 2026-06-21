// 前端组合式业务状态：封装 usePagination 相关轮询、弹窗、分页或连接状态。
import { ref, watch } from 'vue'

/**
 * @param {Function} fetchFn — async function that returns { data, total } from API
 * @param {Object} options
 * @param {number} [options.pageSize=10]
 * @param {Object} [options.filters] — reactive filters object (e.g. { status, type, search })
 */
// 前端业务函数：协调 usePagination 对应的页面流程、接口调用或状态转换。
export function usePagination(fetchFn, { pageSize = 10, filters = {} } = {}) {
  const data = ref([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const error = ref(null)

  // 前端业务函数：协调 fetch 对应的页面流程、接口调用或状态转换。
  async function fetch(resetPage = false) {
    if (resetPage) page.value = 1
    loading.value = true
    error.value = null
    try {
      const skip = (page.value - 1) * pageSize
      const result = await fetchFn({ skip, limit: pageSize, page: page.value, ...filters })
      data.value = result.data ?? []
      total.value = result.total ?? 0
    } catch (e) {
      error.value = e
      data.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  // 前端业务函数：协调 goToPage 对应的页面流程、接口调用或状态转换。
  function goToPage(p) {
    if (p < 1 || p > totalPages.value) return
    page.value = p
    fetch()
  }

  // 前端业务函数：协调 reset 对应的页面流程、接口调用或状态转换。
  function reset() {
    page.value = 1
    data.value = []
    total.value = 0
    error.value = null
  }

  const totalPages = () => Math.ceil(total.value / pageSize)

  // Auto-refetch when page or filters change
  if (filters && typeof filters === 'object') {
    const filterKeys = Object.keys(filters)
    if (filterKeys.length > 0) {
      watch(
        () => filterKeys.map(k => filters[k]),
        () => fetch(true),
        { deep: true }
      )
    }
  }

  return { data, total, page, loading, error, fetch, goToPage, reset, totalPages }
}
