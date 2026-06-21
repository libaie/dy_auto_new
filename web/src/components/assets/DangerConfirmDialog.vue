<!-- 素材业务组件：展示或处理素材详情、参考图、AI 改写和危险操作确认。 -->
<script setup>
import AppDialog from '../ui/AppDialog.vue'
import AppButton from '../ui/AppButton.vue'

defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '确认危险操作' },
  message: { type: String, default: '此操作可能影响现有生产记录，请确认后继续。' },
  impact: { type: String, default: '' },
  confirmText: { type: String, default: '确认执行' },
  cancelText: { type: String, default: '取消' },
})

const emit = defineEmits(['confirm', 'cancel'])

function cancel() {
  emit('cancel')
}
</script>

<template>
  <AppDialog :open="open" :title="title" max-width="max-w-md" @close="cancel">
    <div class="mt-4 space-y-4">
      <p class="text-sm text-slate-300">{{ message }}</p>
      <p v-if="impact" class="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
        {{ impact }}
      </p>
      <div class="flex justify-end gap-2">
        <AppButton type="button" variant="secondary" @click="cancel">{{ cancelText }}</AppButton>
        <AppButton type="button" variant="danger" @click="emit('confirm')">{{ confirmText }}</AppButton>
      </div>
    </div>
  </AppDialog>
</template>
