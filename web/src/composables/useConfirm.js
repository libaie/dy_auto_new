// 前端组合式业务状态：封装 useConfirm 相关轮询、弹窗、分页或连接状态。
import { ref } from 'vue'

export function useConfirm() {
  const isOpen = ref(false)
  const title = ref('')
  const message = ref('')
  const danger = ref(false)
  const confirmAction = ref(null)

  // 前端业务函数：协调 open 对应的页面流程、接口调用或状态转换。
  function open(opts, action) {
    title.value = opts.title || ''
    message.value = opts.message || ''
    danger.value = opts.danger || false
    confirmAction.value = action
    isOpen.value = true
  }

  // 前端业务函数：协调 handleConfirm 对应的页面流程、接口调用或状态转换。
  async function handleConfirm() {
    if (confirmAction.value) {
      await confirmAction.value()
    }
    isOpen.value = false
  }

  // 前端业务函数：协调 handleCancel 对应的页面流程、接口调用或状态转换。
  function handleCancel() {
    isOpen.value = false
  }

  return { isOpen, title, message, danger, open, handleConfirm, handleCancel }
}
