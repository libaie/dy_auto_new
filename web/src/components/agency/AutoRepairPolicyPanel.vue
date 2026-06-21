<!-- 专家团队业务组件：展示或操作专家团队、审查、返修和创意补丁相关业务状态。 -->
<template>
  <section class="rounded-lg border border-white/10 bg-slate-950/70 p-4" data-test="auto-repair-policy">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-sm font-semibold text-slate-100">{{ copy.policyTitle }}</h2>
        <p class="mt-1 text-xs leading-5 text-slate-400">{{ copy.paidRepairWarning }}</p>
      </div>
      <label class="inline-flex items-center gap-2 text-sm text-slate-200">
        <input
          data-test="auto-repair-enabled"
          :checked="modelValue.enabled"
          type="checkbox"
          class="accent-emerald-500"
          @change="update({ enabled: $event.target.checked })"
        />
        {{ modelValue.enabled ? copy.policyEnabled : copy.policyDisabled }}
      </label>
    </div>

    <div class="mt-4 grid gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
      <label class="block text-xs text-slate-400">
        {{ copy.budgetLabel }}
        <input
          data-test="auto-repair-budget"
          :value="modelValue.budget_limit"
          type="number"
          min="0"
          step="0.01"
          class="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-400"
          @input="update({ budget_limit: Number($event.target.value || 0) })"
        />
      </label>
      <div class="rounded border border-slate-800 bg-slate-900/60 p-3 text-xs leading-5 text-slate-300">
        <div class="font-medium text-slate-100">{{ copy.allowedScope }}</div>
        <div class="mt-1">
          风格锁定、分镜补参考、供应商同步失败等确定性问题可自动处理；角色/场景参考图等付费返修必须先通过预算与人工确认。
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { AUTO_REPAIR_COPY as copy } from '../../constants/autoRepairCopy.js'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({ enabled: true, budget_limit: 0 }),
  },
})
const emit = defineEmits(['update:modelValue'])

function update(patch) {
  emit('update:modelValue', {
    ...props.modelValue,
    ...patch,
  })
}
</script>
