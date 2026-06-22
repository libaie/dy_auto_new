// 前端组合式业务状态：封装 useDialog 相关轮询、弹窗、分页或连接状态。
import { ref, reactive } from 'vue'

/**
 * @param {Object} defaultForm — default values for the form
 */
// 前端业务函数：协调 useDialog 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 useDialog 对应业务流程的处理结果。
export function useDialog(defaultForm = {}) {
  const isOpen = ref(false)
  const isEditing = ref(false)
  const saving = ref(false)
  const error = ref(null)
  const editingId = ref(null)
  const form = reactive({ ...defaultForm })

  // 前端业务函数：协调 open 对应的页面流程、接口调用或状态转换。
  // 入参：data 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 open 对应业务流程的处理结果。
  function open(data = null) {
    if (data) {
      isEditing.value = true
      editingId.value = data.id ?? null
      Object.assign(form, data)
    } else {
      isEditing.value = false
      editingId.value = null
      Object.assign(form, defaultForm)
    }
    error.value = null
    isOpen.value = true
  }

  // 前端业务函数：协调 close 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 close 对应业务流程的处理结果。
  function close() {
    isOpen.value = false
    error.value = null
    Object.assign(form, defaultForm)
  }

  // 前端业务函数：协调 reset 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 reset 对应业务流程的处理结果。
  function reset() {
    Object.assign(form, defaultForm)
    error.value = null
  }

  return { isOpen, isEditing, saving, error, editingId, form, open, close, reset }
}
