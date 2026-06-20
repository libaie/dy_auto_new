<template>
  <div class="flex flex-wrap gap-2">
    <button
      data-action="save"
      type="button"
      class="rounded-md border border-sky-400/50 px-3 py-1.5 text-xs font-medium text-sky-100 hover:bg-sky-400/10 focus:outline-none focus:ring-2 focus:ring-sky-300 disabled:opacity-50"
      :disabled="disabled"
      @click="$emit('save')"
    >
      保存修改
    </button>
    <button
      data-action="approve"
      type="button"
      class="rounded-md border border-emerald-300/50 px-3 py-1.5 text-xs font-medium text-emerald-100 hover:bg-emerald-300/10 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:opacity-50"
      :disabled="disabled"
      @click="$emit('approve')"
    >
      批准
    </button>
    <button
      data-action="apply"
      type="button"
      class="rounded-md border border-cyan-300/50 px-3 py-1.5 text-xs font-medium text-cyan-100 hover:bg-cyan-300/10 focus:outline-none focus:ring-2 focus:ring-cyan-300 disabled:opacity-50"
      :disabled="disabled"
      @click="$emit('apply')"
    >
      应用
    </button>
    <button
      data-action="reject"
      type="button"
      class="rounded-md border border-rose-300/50 px-3 py-1.5 text-xs font-medium text-rose-100 hover:bg-rose-300/10 focus:outline-none focus:ring-2 focus:ring-rose-300 disabled:opacity-50"
      :disabled="disabled"
      @click="$emit('reject')"
    >
      拒绝
    </button>
    <button
      v-if="sourceInvocationId"
      data-action="open-invocation"
      type="button"
      class="rounded-md border border-white/10 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-zinc-300 disabled:opacity-50"
      :disabled="disabled"
      @click="$emit('open-invocation')"
    >
      来源调用
    </button>
  </div>
</template>

<script setup>
defineProps({
  disabled: { type: Boolean, default: false },
  sourceInvocationId: { type: String, default: '' },
})

defineEmits(['save', 'approve', 'apply', 'reject', 'open-invocation'])
</script>
