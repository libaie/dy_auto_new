<template>
  <section class="rounded-lg border border-cyan-400/20 bg-cyan-950/20 p-3" data-test="creative-patch-summary">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-sm font-semibold text-cyan-50">创作补丁</h2>
        <p class="mt-1 text-xs leading-5 text-cyan-100/80">{{ hintText }}</p>
      </div>
      <div class="flex flex-wrap gap-2 text-xs">
        <span class="rounded border border-white/10 px-2 py-1 text-zinc-100">全部 {{ total }}</span>
        <span class="rounded border border-amber-300/30 px-2 py-1 text-amber-100">待处理 {{ blockingCount }}</span>
        <span class="rounded border border-emerald-300/30 px-2 py-1 text-emerald-100">已应用 {{ applied }}</span>
        <span class="rounded border border-zinc-500/40 px-2 py-1 text-zinc-300">已拒绝 {{ rejected }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
})

const total = computed(() => Number(props.summary.total || 0))
const blockingCount = computed(() => Number(props.summary.blocking || props.summary.proposed || 0))
const applied = computed(() => Number(props.summary.applied || 0))
const rejected = computed(() => Number(props.summary.rejected || 0))
const hintText = computed(() => {
  if (!total.value) return '当前没有专家改稿补丁。'
  if (blockingCount.value) return '存在生成前需要确认的改稿补丁。'
  return '补丁已处理，后续生成可继续推进。'
})
</script>
