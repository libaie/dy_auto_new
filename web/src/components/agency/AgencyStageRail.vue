<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <nav class="min-w-0 overflow-hidden rounded-lg border border-white/10 bg-zinc-900/80 p-4" aria-label="生产阶段">
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-white">阶段流转</h2>
      <p class="mt-1 text-xs leading-5 text-zinc-500">从风格锁定到合成交付，逐段追踪质量门。</p>
    </div>

    <ol v-if="stages.length" class="flex w-full min-w-0 gap-3 overflow-x-auto pb-1 2xl:block 2xl:space-y-3 2xl:overflow-visible">
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

// 前端业务函数：协调 stageClass 对应的页面流程、接口调用或状态转换。
// 入参：status 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 stageClass 对应业务流程的处理结果。
function stageClass(status) {
  const normalized = normalizeStatus(status)
  if (['running', 'in_progress', 'image_batch_running', 'video_batch_running', 'composing'].includes(normalized)) return 'border-cyan-400/40 bg-cyan-950/30'
  if (['failed', 'failure', 'blocked', 'rejected', 'failed_retryable'].includes(normalized)) return 'border-rose-400/40 bg-rose-950/30'
  if (['completed', 'complete', 'passed', 'pass', 'approved'].includes(normalized)) return 'border-emerald-400/30 bg-emerald-950/20'
  return 'border-white/10 bg-zinc-950/60'
}

// 前端业务函数：协调 markerClass 对应的页面流程、接口调用或状态转换。
// 入参：status 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 markerClass 对应业务流程的处理结果。
function markerClass(status) {
  const normalized = normalizeStatus(status)
  if (['running', 'in_progress', 'image_batch_running', 'video_batch_running', 'composing'].includes(normalized)) return 'border-cyan-300/60 bg-cyan-300/10 text-cyan-100'
  if (['failed', 'failure', 'blocked', 'rejected', 'failed_retryable'].includes(normalized)) return 'border-rose-300/60 bg-rose-300/10 text-rose-100'
  if (['completed', 'complete', 'passed', 'pass', 'approved'].includes(normalized)) return 'border-emerald-300/50 bg-emerald-300/10 text-emerald-100'
  return 'border-white/10 bg-zinc-800 text-zinc-300'
}

// 前端业务函数：协调 stageLabel 对应的页面流程、接口调用或状态转换。
// 入参：stage 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 stageLabel 对应业务流程的处理结果。
function stageLabel(stage) {
  return phaseLabel(stage.stage, stage.label)
}

// 前端业务函数：协调 normalizeStatus 对应的页面流程、接口调用或状态转换。
// 入参：status 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 normalizeStatus 对应业务流程的处理结果。
function normalizeStatus(status) {
  return String(status || '').trim().toLowerCase()
}
</script>
