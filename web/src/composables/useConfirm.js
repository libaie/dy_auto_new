// 前端组合式业务状态：封装 useConfirm 相关轮询、弹窗、分页或连接状态。
import { ref } from 'vue'

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 useConfirm 对应业务流程的处理结果。
export function useConfirm() {
  const isOpen = ref(false)
  const title = ref('')
  const message = ref('')
  const danger = ref(false)
  const confirmAction = ref(null)

  // 前端业务函数：协调 open 对应的页面流程、接口调用或状态转换。
  // 入参：opts、action 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 open 对应业务流程的处理结果。
  function open(opts, action) {
    title.value = opts.title || ''
    message.value = opts.message || ''
    danger.value = opts.danger || false
    confirmAction.value = action
    isOpen.value = true
  }

  // 前端业务函数：协调 handleConfirm 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 handleConfirm 对应业务流程的处理结果。
  async function handleConfirm() {
    if (confirmAction.value) {
      await confirmAction.value()
    }
    isOpen.value = false
  }

  // 前端业务函数：协调 handleCancel 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 handleCancel 对应业务流程的处理结果。
  function handleCancel() {
    isOpen.value = false
  }

  return { isOpen, title, message, danger, open, handleConfirm, handleCancel }
}
