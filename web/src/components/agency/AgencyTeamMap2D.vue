<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <aside class="rounded-lg border border-white/10 bg-zinc-900/80 p-4">
    <div class="mb-4">
      <h2 class="text-lg font-semibold text-white">专家席位地图</h2>
      <p class="mt-1 text-xs leading-5 text-zinc-500">
        {{ currentExperts.length }} 位当前视频专家按阶段接力，质量审查专家只在对应阶段亮起。
      </p>
    </div>

    <div v-if="currentExperts.length" class="space-y-3">
      <section
        v-for="group in visibleGroups"
        :key="group.key"
        class="rounded-md border border-white/10 bg-zinc-950/55 p-3"
      >
        <div class="mb-2 flex items-start justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-zinc-100">{{ group.label }} · {{ group.items.length }}</h3>
            <p class="mt-1 text-xs leading-5 text-zinc-500">{{ group.detail }}</p>
          </div>
        </div>

        <div class="grid gap-2">
          <button
            v-for="expert in group.items"
            :key="expert.expert_id"
            :data-expert-id="expert.expert_id"
            class="group rounded-md border border-white/10 bg-zinc-900/75 p-3 text-left hover:border-cyan-300/60 hover:bg-zinc-900"
            @click="$emit('select', expert.expert_id)"
          >
            <div class="flex items-start gap-3">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-zinc-800 text-sm font-semibold text-cyan-100 group-hover:border-cyan-300/60">
                {{ expertAvatar(expert.expert_id) }}
              </div>
              <div class="min-w-0">
                <div class="font-medium text-zinc-100">{{ expertName(expert.expert_id, expert.name) }}</div>
                <div class="mt-1 text-xs leading-5 text-zinc-400">{{ phaseText(expert.phases || expert.phase || []) }}</div>
              </div>
            </div>
          </button>
        </div>
      </section>
    </div>

    <div v-else class="rounded-md border border-white/10 bg-zinc-950/60 p-5 text-sm text-zinc-400">
      暂无当前专家档案。
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import {
  ROLE_GROUPS,
  expertAvatar,
  expertName,
  expertRoleGroup,
  isLegacyExpert,
  phaseText,
} from './agencyExpertLabels.js'

const props = defineProps({
  experts: { type: Array, default: () => [] },
})

defineEmits(['select'])

const currentExperts = computed(() => (
  props.experts.filter(expert => expert?.expert_id && !expert.legacy && !isLegacyExpert(expert.expert_id))
))

const visibleGroups = computed(() => (
  ['core', 'quality', 'support']
    .map(key => ({
      ...ROLE_GROUPS[key],
      items: currentExperts.value.filter(expert => expertRoleGroup(expert) === key),
    }))
    .filter(group => group.items.length)
))
</script>
