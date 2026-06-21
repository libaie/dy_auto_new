<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <section v-if="patch" class="rounded-lg border border-white/10 bg-zinc-950/70 p-3">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold text-zinc-100">{{ patch.title || '未命名补丁' }}</h3>
        <p class="mt-1 text-xs leading-5 text-zinc-400">{{ patch.reason || '暂无原因' }}</p>
      </div>
      <span class="rounded border border-white/10 px-2 py-1 text-xs text-zinc-300">{{ statusLabel(patch.status) }}</span>
    </div>

    <div class="mt-3 space-y-3">
      <div
        v-for="field in fields"
        :key="field"
        class="grid gap-2 rounded-md border border-white/10 bg-zinc-900/60 p-3 md:grid-cols-2"
      >
        <div>
          <div class="text-[11px] font-medium uppercase tracking-normal text-zinc-500">{{ field }}</div>
          <pre class="mt-1 max-h-36 overflow-auto whitespace-pre-wrap break-words rounded border border-white/10 bg-zinc-950 p-2 text-xs leading-5 text-zinc-300">{{ displayValue(beforeValue(field)) }}</pre>
        </div>
        <label class="block">
          <span class="text-[11px] font-medium uppercase tracking-normal text-cyan-300">after</span>
          <textarea
            v-if="typeof afterValue(field) === 'string'"
            :data-field="field"
            class="mt-1 min-h-24 w-full rounded border border-white/10 bg-zinc-950 p-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-cyan-300"
            :value="afterValue(field)"
            @input="updateField(field, $event.target.value)"
          />
          <p v-if="typeof afterValue(field) === 'string'" class="mt-1 break-words text-xs leading-5 text-zinc-500">
            {{ afterValue(field) || '空' }}
          </p>
          <pre v-else class="mt-1 max-h-36 overflow-auto whitespace-pre-wrap break-words rounded border border-white/10 bg-zinc-950 p-2 text-xs leading-5 text-zinc-100">{{ displayValue(afterValue(field)) }}</pre>
        </label>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  patch: { type: Object, default: null },
  after: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:after'])

const fields = computed(() => {
  const before = Object.keys(props.patch?.before || {})
  const after = Object.keys(props.after || {})
  return Array.from(new Set([...before, ...after]))
})

function beforeValue(field) {
  return props.patch?.before?.[field]
}

function afterValue(field) {
  return props.after?.[field]
}

function updateField(field, value) {
  emit('update:after', { ...(props.after || {}), [field]: value })
}

function displayValue(value) {
  if (value === undefined || value === null || value === '') return '空'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function statusLabel(status) {
  const labels = {
    proposed: '待处理',
    edited: '已编辑',
    approved: '已批准',
    applied: '已应用',
    rejected: '已拒绝',
  }
  return labels[status] || status || '未知'
}
</script>
