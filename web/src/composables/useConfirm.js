import { ref } from 'vue'

export function useConfirm() {
  const isOpen = ref(false)
  const title = ref('')
  const message = ref('')
  const danger = ref(false)
  const confirmAction = ref(null)

  function open(opts, action) {
    title.value = opts.title || ''
    message.value = opts.message || ''
    danger.value = opts.danger || false
    confirmAction.value = action
    isOpen.value = true
  }

  async function handleConfirm() {
    if (confirmAction.value) {
      await confirmAction.value()
    }
    isOpen.value = false
  }

  function handleCancel() {
    isOpen.value = false
  }

  return { isOpen, title, message, danger, open, handleConfirm, handleCancel }
}
