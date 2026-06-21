<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <span class="inline-flex min-h-6 items-center rounded-md border px-2 text-xs font-medium" :class="classes">
    {{ text }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { statusLabel } from './agencyExpertLabels.js'

const props = defineProps({
  status: { type: String, default: 'pending' },
})

const CLASS_MAP = {
  pending: 'border-white/10 bg-zinc-800 text-zinc-300',
  queued: 'border-white/10 bg-zinc-800 text-zinc-300',
  running: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
  completed: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
  complete: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
  passed: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
  pass: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
  ready: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
  warning: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  warn: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  partial: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  blocked: 'border-rose-300/30 bg-rose-400/10 text-rose-100',
  failed: 'border-rose-300/30 bg-rose-400/10 text-rose-100',
  missing: 'border-white/10 bg-zinc-800 text-zinc-300',
  legacy_summary: 'border-violet-300/30 bg-violet-400/10 text-violet-100',
  image_batch_running: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
  video_batch_running: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
  image_review_pending: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  video_review_pending: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  image_human_review_required: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  video_human_review_required: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  final_review_pending: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  review_pending: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  rejected: 'border-rose-300/30 bg-rose-400/10 text-rose-100',
  regenerating: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
  retry_queued: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  failed_retryable: 'border-rose-300/30 bg-rose-400/10 text-rose-100',
  composing: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
}

const normalizedStatus = computed(() => String(props.status || '').trim().toLowerCase())
const text = computed(() => statusLabel(normalizedStatus.value))
const classes = computed(() => CLASS_MAP[normalizedStatus.value] || CLASS_MAP.pending)
</script>
