import { ref, reactive } from 'vue'

/**
 * @param {Object} defaultForm — default values for the form
 */
export function useDialog(defaultForm = {}) {
  const isOpen = ref(false)
  const isEditing = ref(false)
  const saving = ref(false)
  const error = ref(null)
  const editingId = ref(null)
  const form = reactive({ ...defaultForm })

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

  function close() {
    isOpen.value = false
    error.value = null
    Object.assign(form, defaultForm)
  }

  function reset() {
    Object.assign(form, defaultForm)
    error.value = null
  }

  return { isOpen, isEditing, saving, error, editingId, form, open, close, reset }
}
