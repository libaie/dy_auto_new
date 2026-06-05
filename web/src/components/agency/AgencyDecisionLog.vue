<template>
  <section class="rounded-lg border border-white/10 bg-zinc-900/80 p-4">
    <div class="mb-3 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-white">决策日志</h2>
        <p class="mt-1 text-xs leading-5 text-zinc-500">
          记录专家结论、质量发现、返修要求和下一步动作，避免后台暗箱操作。
        </p>
      </div>
      <span class="rounded border border-white/10 bg-zinc-950 px-2 py-1 text-xs text-zinc-400">{{ items.length }} 条</span>
    </div>

    <div v-if="items.length" class="mb-3 flex flex-wrap gap-2">
      <button
        v-for="option in filterOptions"
        :key="option.key"
        type="button"
        :data-filter-scope="option.key"
        class="rounded-md border px-3 py-1.5 text-xs font-medium transition"
        :class="activeFilter === option.key ? 'border-cyan-300 bg-cyan-300 text-zinc-950' : 'border-white/10 bg-zinc-950 text-zinc-300 hover:border-cyan-300/60 hover:text-white'"
        @click="activeFilter = option.key"
      >
        {{ option.label }}
      </button>
    </div>

    <div v-if="!filteredItems.length" class="rounded-md border border-white/10 bg-zinc-950/60 p-5 text-sm text-zinc-400">
      暂无符合筛选条件的专家决策日志。
    </div>

    <div v-else class="space-y-3">
      <article
        v-for="item in filteredItems"
        :key="item.invocation_id || item.id"
        class="rounded-md border border-white/10 bg-zinc-950/65 p-3"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-zinc-100">{{ stageName(item.stage) }}</span>
              <span class="text-xs text-zinc-500">/</span>
              <span class="text-sm text-zinc-200">{{ expertName(item.expert_id, item.expert_name) }}</span>
              <span
                v-if="isHistorical(item)"
                class="rounded border border-violet-300/30 bg-violet-400/10 px-2 py-0.5 text-[11px] text-violet-100"
              >
                历史审查记录
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-zinc-300">{{ decisionText(item.decision || item.summary || item.repair_action) }}</p>
          </div>
          <AgencyStatusBadge :status="item.result_status || item.status" />
        </div>

        <div class="mt-3 grid gap-2 text-xs leading-5 text-zinc-400 md:grid-cols-2">
          <p v-if="listText(item.findings, '暂无明确发现', 'finding')">
            <span class="text-zinc-300">发现：</span>{{ listText(item.findings, '暂无明确发现', 'finding') }}
          </p>
          <p v-if="listText(item.required_changes, '暂无返修要求', 'required_change')">
            <span class="text-zinc-300">必须修改：</span>{{ listText(item.required_changes, '暂无返修要求', 'required_change') }}
          </p>
          <p v-if="listText(item.evidence, '暂无证据', 'evidence')">
            <span class="text-zinc-300">证据：</span>{{ listText(item.evidence, '暂无证据', 'evidence') }}
          </p>
          <p v-if="item.next_action">
            <span class="text-zinc-300">下一步：</span>{{ cleanText(item.next_action, 'next_action', '等待下一步处理') }}
          </p>
        </div>

        <AutoRepairTaskList
          v-if="repairTasks(item).length"
          class="mt-3"
          :tasks="repairTasks(item)"
          @manual-action="$emit('manual-action', $event)"
          @retry="$emit('retry', $event)"
        />
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import AgencyStatusBadge from './AgencyStatusBadge.vue'
import AutoRepairTaskList from './AutoRepairTaskList.vue'
import {
  decisionLogText,
  expertName as knownExpertName,
  isLegacyExpert,
  phaseLabel,
} from './agencyExpertLabels.js'

defineEmits(['manual-action', 'retry'])

const props = defineProps({
  items: { type: Array, default: () => [] },
  expertTeam: { type: Array, default: () => [] },
  stages: { type: Array, default: () => [] },
})

const activeFilter = ref('all')

const filterOptions = [
  { key: 'all', label: '全部' },
  { key: 'current_team', label: '当前审查' },
  { key: 'historical_audit', label: '历史审计' },
]

const expertNames = computed(() => Object.fromEntries(
  props.expertTeam.map(item => [item.expert_id, item.name]).filter(([id]) => id)
))

const stageNames = computed(() => Object.fromEntries(
  props.stages.map(item => [item.stage, item.label]).filter(([stage]) => stage)
))

const filteredItems = computed(() => {
  if (activeFilter.value === 'current_team') return props.items.filter(item => !isHistorical(item))
  if (activeFilter.value === 'historical_audit') return props.items.filter(isHistorical)
  return props.items
})

const DECISION_TEXT = {
  pass: '通过检查',
  passed: '通过检查',
  ok: '通过检查',
  warn: '存在警告',
  warning: '存在警告',
  blocked: '已阻断',
  failed: '未通过',
  legacy_summary: '已记录历史审计结论',
}

function stageName(stage) {
  return phaseLabel(stage, stageNames.value[stage])
}

function expertName(id, fallback = '') {
  return knownExpertName(id, expertNames.value[id] || fallback)
}

function decisionText(value) {
  const key = String(value || '').toLowerCase()
  if (DECISION_TEXT[key]) return DECISION_TEXT[key]
  return cleanText(value, 'decision', '专家结论待补充')
}

function cleanText(value, field, fallback) {
  return decisionLogText(value, field, fallback)
}

function listText(value, fallback = '', field = 'generic') {
  if (!value) return ''
  const values = Array.isArray(value) ? value : [value]
  const seen = new Set()
  const labels = values
    .map(item => cleanText(item, field, fallback || ''))
    .filter(Boolean)
    .filter(item => {
      if (seen.has(item)) return false
      seen.add(item)
      return true
    })
  return labels.length ? labels.join('；') : fallback
}

function repairTasks(item) {
  return item?.repair_tasks || item?.output_summary_json?.repair_tasks || []
}

function isHistorical(item) {
  return Boolean(item?.legacy || item?.display_scope === 'historical_audit' || isLegacyExpert(item?.expert_id))
}
</script>
