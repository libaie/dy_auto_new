<template>
  <section class="rounded-lg border border-white/10 bg-zinc-900/80 p-4">
    <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-white">专家调用拓扑</h2>
        <p class="mt-1 text-xs leading-5 text-zinc-500">阶段协作编排：并行审阅、主责汇总、质量门禁全部可追踪。</p>
      </div>
      <span class="rounded border border-white/10 bg-zinc-950 px-2 py-1 text-xs text-zinc-300">{{ summaryText }}</span>
    </div>

    <div v-if="!invocations.length" class="mb-3 rounded-md border border-white/10 bg-zinc-950/60 p-5 text-sm text-zinc-400">
      暂无专家调用记录。
    </div>

    <div class="grid gap-3 xl:grid-cols-5">
      <article
        v-for="stage in stages"
        :key="stage.stage"
        class="rounded-md border border-white/10 bg-zinc-950/70 p-3"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h3 class="text-sm font-semibold text-zinc-100">{{ stageLabel(stage) }}</h3>
            <div class="mt-1 text-xs text-zinc-500">{{ invocationCount(stage) }}</div>
          </div>
          <AgencyStatusBadge :status="stage.status" />
        </div>

        <div class="mt-3 space-y-3 text-xs">
          <section>
            <div class="mb-1 text-zinc-500">并行审阅</div>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="id in currentIds(stage.reviewers)"
                :key="`${stage.stage}-${id}-review`"
                :data-expert-id="id"
                class="min-h-8 rounded border border-violet-400/30 bg-violet-400/10 px-2 py-1 text-left text-violet-100 hover:border-violet-200"
                @click="$emit('selectExpert', id)"
              >
                {{ expertName(id) }}
              </button>
              <span v-if="!currentIds(stage.reviewers).length" class="text-zinc-600">暂无并行审阅</span>
            </div>
          </section>

          <section>
            <div class="mb-1 text-zinc-500">主责汇总</div>
            <button
              v-if="isCurrentId(stage.lead)"
              :data-expert-id="stage.lead"
              class="min-h-8 rounded border border-cyan-400/40 bg-cyan-400/10 px-2 py-1 text-left text-cyan-100 hover:border-cyan-200"
              @click="$emit('selectExpert', stage.lead)"
            >
              {{ expertName(stage.lead) }}
            </button>
            <span v-else class="text-zinc-600">暂未指定</span>
          </section>

          <section>
            <div class="mb-1 text-zinc-500">质量门禁</div>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="id in currentIds(stage.qa)"
                :key="`${stage.stage}-${id}-qa`"
                :data-expert-id="id"
                class="min-h-8 rounded border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-left text-emerald-100 hover:border-emerald-200"
                @click="$emit('selectExpert', id)"
              >
                {{ expertName(id) }}
              </button>
              <span v-if="!currentIds(stage.qa).length" class="text-zinc-600">暂无质量门禁</span>
            </div>
          </section>
        </div>

        <div v-if="stageInvocations(stage).length" class="mt-3 space-y-2 border-t border-white/10 pt-3">
          <button
            v-for="item in stageInvocations(stage)"
            :key="item.id || item.invocation_id"
            :data-expert-id="item.expert_id"
            class="w-full rounded-md border border-white/10 bg-zinc-900 p-2 text-left hover:border-cyan-400/50 hover:bg-zinc-800"
            @click="$emit('selectExpert', item.expert_id)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-xs font-medium text-zinc-100">{{ expertName(item.expert_id) }}</span>
              <AgencyStatusBadge :status="item.result_status || item.execution_status" />
            </div>
            <p v-if="item.summary" class="mt-1 text-xs leading-5 text-zinc-400">{{ safeDisplayText(item.summary, '已记录专家结论') }}</p>
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AgencyStatusBadge from './AgencyStatusBadge.vue'
import {
  expertName as knownExpertName,
  isCurrentExpert,
  isLegacyExpert,
  phaseLabel,
  safeDisplayText,
} from './agencyExpertLabels.js'

const props = defineProps({
  stages: { type: Array, default: () => [] },
  expertTeam: { type: Array, default: () => [] },
  invocations: { type: Array, default: () => [] },
})

defineEmits(['selectExpert'])

const summaryText = computed(() => (
  props.invocations.length ? `已记录 ${props.invocations.length} 次调用` : '等待专家调用'
))

const expertNames = computed(() => Object.fromEntries(
  props.expertTeam.map(item => [item.expert_id, item.name]).filter(([id]) => id)
))

function stageLabel(stage) {
  return phaseLabel(stage.stage, stage.label)
}

function expertName(id) {
  return knownExpertName(id, expertNames.value[id])
}

function normalizeIds(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.flatMap(normalizeIds)
  if (typeof value === 'object') return normalizeIds(value.expert_id || value.expert_ids || value.id)
  return [String(value)].filter(Boolean)
}

function isCurrentId(id) {
  return Boolean(id && isCurrentExpert(id) && !isLegacyExpert(id))
}

function currentIds(value) {
  return normalizeIds(value).filter(isCurrentId)
}

function stageInvocations(stage) {
  return props.invocations.filter(item => item.stage === stage.stage && isCurrentId(item.expert_id))
}

function invocationCount(stage) {
  const count = stageInvocations(stage).length
  return count ? `${count} 条调用记录` : '未记录调用'
}
</script>
