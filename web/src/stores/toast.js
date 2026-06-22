// 前端状态仓库：维护 toast 相关登录态、消息提示或跨页面状态。
import { defineStore } from 'pinia'
import { ref } from 'vue'

let _nextId = 0

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])

  // 前端业务函数：协调 addToast 对应的页面流程、接口调用或状态转换。
  // 入参：message 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 addToast 对应业务流程的处理结果。
  function addToast({ type = 'error', message, duration = 4000 }) {
    const id = ++_nextId
    toasts.value.push({ id, type, message })
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration)
    }
  }

  // 前端业务函数：协调 removeToast 对应的页面流程、接口调用或状态转换。
  // 入参：id 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 removeToast 对应业务流程的处理结果。
  function removeToast(id) {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  // 前端业务函数：协调 error 对应的页面流程、接口调用或状态转换。
  // 入参：message、duration 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 error 对应业务流程的处理结果。
  function error(message, duration) {
    addToast({ type: 'error', message, duration })
  }

  // 前端业务函数：协调 warning 对应的页面流程、接口调用或状态转换。
  // 入参：message、duration 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 warning 对应业务流程的处理结果。
  function warning(message, duration) {
    addToast({ type: 'warning', message, duration })
  }

  // 前端业务函数：协调 success 对应的页面流程、接口调用或状态转换。
  // 入参：message、duration 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 success 对应业务流程的处理结果。
  function success(message, duration) {
    addToast({ type: 'success', message, duration })
  }

  // 前端业务函数：协调 info 对应的页面流程、接口调用或状态转换。
  // 入参：message、duration 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 info 对应业务流程的处理结果。
  function info(message, duration) {
    addToast({ type: 'info', message, duration })
  }

  return { toasts, addToast, removeToast, error, warning, success, info }
})
