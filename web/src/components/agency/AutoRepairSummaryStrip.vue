<template>
  <section class="rounded-lg border border-amber-400/30 bg-amber-950/20 p-3" data-test="auto-repair-summary">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-sm font-semibold text-amber-50">{{ copy.summaryTitle }}</h2>
        <p class="mt-1 text-xs leading-5 text-amber-100/80">
          {{ hintText }}
        </p>
      </div>
      <div class="flex flex-wrap gap-2 text-xs">
        <span class="rounded border border-amber-300/30 px-2 py-1 text-amber-100">全部 {{ total }}</span>
        <span class="rounded border border-sky-300/30 px-2 py-1 text-sky-100">进行中 {{ active }}</span>
        <span class="rounded border border-rose-300/30 px-2 py-1 text-rose-100">需人工 {{ manual }}</span>
        <span v-if="costText" class="rounded border border-emerald-300/30 px-2 py-1 text-emerald-100">{{ costText }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { AUTO_REPAIR_COPY as copy, formatRepairCost } from '../../constants/autoRepairCopy.js'

const props = defineProps({
  summary: { type: Object, default: () => ({}) },
})

const total = computed(() => Number(props.summary.total || props.summary.total_count || 0))
const active = computed(() => Number(props.summary.active || props.summary.active_count || props.summary.running || 0))
const manual = computed(() => Number(props.summary.manual_required || props.summary.manual_count || props.summary.blocked || 0))
const costText = computed(() => {
  const cost = Number(props.summary.estimated_cost || props.summary.cost || props.summary.repair_cost || 0)
  return cost > 0 ? formatRepairCost(cost) : ''
})
const hintText = computed(() => {
  if (!total.value) return '当前没有待处理的专家返修任务。'
  if (manual.value) return '存在需要人工确认的返修项，系统不会自动越过审查闸门。'
  if (active.value) return '系统正在处理确定性返修，完成后会回到复审状态。'
  return '返修任务已记录，后续仍以人工审查结果为准。'
})
</script>
