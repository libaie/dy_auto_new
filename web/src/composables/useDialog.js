// 前端组合式业务状态：封装 useDialog 相关轮询、弹窗、分页或连接状态。
import { ref, reactive } from 'vue'

/**
 * @param {Object} defaultForm — default values for the form
 */
// 前端业务函数：协调 useDialog 对应的页面流程、接口调用或状态转换。
export function useDialog(defaultForm = {}) {
  const isOpen = ref(false)
  const isEditing = ref(false)
  const saving = ref(false)
  const error = ref(null)
  const editingId = ref(null)
  const form = reactive({ ...defaultForm })

  // 前端业务函数：协调 open 对应的页面流程、接口调用或状态转换。
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
  function close() {
    isOpen.value = false
    error.value = null
    Object.assign(form, defaultForm)
  }

  // 前端业务函数：协调 reset 对应的页面流程、接口调用或状态转换。
  function reset() {
    Object.assign(form, defaultForm)
    error.value = null
  }

  return { isOpen, isEditing, saving, error, editingId, form, open, close, reset }
}
