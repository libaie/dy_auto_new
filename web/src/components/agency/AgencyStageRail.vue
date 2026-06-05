<template>
  <nav class="rounded-lg border border-white/10 bg-zinc-900/80 p-4" aria-label="生产阶段">
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-white">阶段流转</h2>
      <p class="mt-1 text-xs leading-5 text-zinc-500">从风格锁定到合成交付，逐段追踪质量门。</p>
    </div>

    <ol v-if="stages.length" class="flex gap-3 overflow-x-auto pb-1 2xl:block 2xl:space-y-3 2xl:overflow-visible">
      <li v-for="(stage, index) in stages" :key="stage.stage" class="min-w-44 2xl:min-w-0">
        <div class="relative rounded-md border p-3" :class="stageClass(stage.status)">
          <div class="flex items-start gap-3">
            <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold" :class="markerClass(stage.status)">
              {{ index + 1 }}
            </span>
            <div class="min-w-0">
              <div class="text-sm font-semibold text-zinc-100">{{ stageLabel(stage) }}</div>
              <AgencyStatusBadge class="mt-2" :status="stage.status" />
            </div>
          </div>
        </div>
      </li>
    </ol>
    <div v-else class="rounded-md border border-white/10 bg-zinc-950/60 p-5 text-sm text-zinc-400">
      暂无生产阶段记录。
    </div>
  </nav>
</template>

<script setup>
import AgencyStatusBadge from './AgencyStatusBadge.vue'
import { phaseLabel } from './agencyExpertLabels.js'

defineProps({
  stages: { type: Array, default: () => [] },
})

function stageClass(status) {
  const normalized = normalizeStatus(status)
  if (['running', 'in_progress', 'image_batch_running', 'video_batch_running', 'composing'].includes(normalized)) return 'border-cyan-400/40 bg-cyan-950/30'
  if (['failed', 'failure', 'blocked', 'rejected', 'failed_retryable'].includes(normalized)) return 'border-rose-400/40 bg-rose-950/30'
  if (['completed', 'complete', 'passed', 'pass', 'approved'].includes(normalized)) return 'border-emerald-400/30 bg-emerald-950/20'
  return 'border-white/10 bg-zinc-950/60'
}

function markerClass(status) {
  const normalized = normalizeStatus(status)
  if (['running', 'in_progress', 'image_batch_running', 'video_batch_running', 'composing'].includes(normalized)) return 'border-cyan-300/60 bg-cyan-300/10 text-cyan-100'
  if (['failed', 'failure', 'blocked', 'rejected', 'failed_retryable'].includes(normalized)) return 'border-rose-300/60 bg-rose-300/10 text-rose-100'
  if (['completed', 'complete', 'passed', 'pass', 'approved'].includes(normalized)) return 'border-emerald-300/50 bg-emerald-300/10 text-emerald-100'
  return 'border-white/10 bg-zinc-800 text-zinc-300'
}

function stageLabel(stage) {
  return phaseLabel(stage.stage, stage.label)
}

function normalizeStatus(status) {
  return String(status || '').trim().toLowerCase()
}
</script>
