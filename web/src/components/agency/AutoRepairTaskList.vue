<template>
  <section data-test="auto-repair-task-list">
    <div v-if="loading" class="rounded border border-white/10 bg-zinc-950/60 p-4 text-sm text-zinc-400">
      {{ copy.loadingTasks }}
    </div>
    <div v-else-if="error" class="rounded border border-rose-500/40 bg-rose-950/30 p-4 text-sm text-rose-100">
      {{ error }}
    </div>
    <div v-else-if="!tasks.length" class="rounded border border-white/10 bg-zinc-950/60 p-4 text-sm text-zinc-400">
      {{ copy.emptyTasks }}
    </div>
    <div v-else class="space-y-3">
      <article
        v-for="task in visibleTasks"
        :key="task.id || `${task.type}-${task.target_id || task.stage}`"
        class="rounded-lg border border-white/10 bg-zinc-950/70 p-3"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-sm font-semibold text-zinc-100">{{ typeLabel(task.type) }}</h3>
              <span class="rounded border border-white/10 px-2 py-0.5 text-[11px] text-zinc-300">{{ statusLabel(task.status) }}</span>
              <span v-if="task.recheck_required" class="rounded border border-sky-300/30 bg-sky-400/10 px-2 py-0.5 text-[11px] text-sky-100">
                {{ copy.recheckPending }}
              </span>
            </div>
            <p class="mt-2 text-sm leading-6 text-zinc-300">
              <span class="text-zinc-500">{{ copy.originalFinding }}：</span>{{ text(task.reason, '专家发现缺少可执行说明') }}
            </p>
          </div>
          <div class="text-right text-xs text-zinc-400">
            <div>{{ copy.costImpact }}</div>
            <div class="mt-1 font-mono text-zinc-100">{{ formatRepairCost(task.estimated_cost) }}</div>
          </div>
        </div>

        <div class="mt-3 grid gap-2 text-xs leading-5 text-zinc-400 md:grid-cols-2">
          <p>
            <span class="text-zinc-300">{{ copy.repairAction }}：</span>{{ text(task.repair_action_label, '等待人工选择处理方式') }}
          </p>
          <p>
            <span class="text-zinc-300">{{ copy.expectedResult }}：</span>{{ text(task.expected_result, '完成后返回审查闸门') }}
          </p>
          <p>
            <span class="text-zinc-300">{{ copy.nextGate }}：</span>{{ task.recheck_required ? copy.recheckPending : copy.repairGate }}
          </p>
          <p v-if="affectedTextFor(task)">
            <span class="text-zinc-300">影响对象：</span>{{ affectedTextFor(task) }}
          </p>
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <button
            v-if="canRetry(task)"
            type="button"
            class="rounded-md border border-sky-400/50 px-3 py-1.5 text-xs font-medium text-sky-100 hover:bg-sky-400/10 focus:outline-none focus:ring-2 focus:ring-sky-300"
            :disabled="busyId === task.id"
            @click="handleRetry(task)"
          >
            {{ primaryLabel(task) }}
          </button>
          <button
            v-if="task.repair_route"
            type="button"
            class="rounded-md border border-amber-300/50 px-3 py-1.5 text-xs font-medium text-amber-100 hover:bg-amber-300/10 focus:outline-none focus:ring-2 focus:ring-amber-300"
            @click="$emit('manual-action', task)"
          >
            {{ text(task.repair_action_label, copy.manualAction) }}
          </button>
          <span v-if="!task.repair_route && !canRetry(task)" class="rounded border border-white/10 px-3 py-1.5 text-xs text-zinc-500">
            {{ copy.noRoute }}
          </span>
        </div>
      </article>

      <button
        v-if="hasHiddenTasks"
        type="button"
        class="rounded-md border border-white/10 px-3 py-1.5 text-xs text-zinc-200 hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-cyan-300"
        @click="expanded = !expanded"
      >
        {{ expanded ? copy.collapse : `${copy.showAll}（${tasks.length}）` }}
      </button>

      <div
        v-if="confirmTask"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="dialogTitleId"
        @keydown.esc="closePaidConfirm"
      >
        <form class="w-full max-w-md rounded-lg border border-amber-300/30 bg-zinc-950 p-4 shadow-xl" @submit.prevent="confirmPaidRetry">
          <h2 :id="dialogTitleId" class="text-base font-semibold text-zinc-100">{{ copy.paidConfirmTitle }}</h2>
          <p class="mt-2 text-sm leading-6 text-zinc-300">{{ copy.paidConfirmBody }}</p>
          <label class="mt-4 block text-xs text-zinc-400">
            {{ copy.paidConfirmReason }}
            <textarea
              ref="reasonInput"
              v-model="confirmReason"
              class="mt-1 min-h-20 w-full rounded border border-white/10 bg-zinc-900 p-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-300"
            />
          </label>
          <label class="mt-3 block text-xs text-zinc-400">
            {{ copy.paidConfirmBudget }}
            <input
              v-model.number="confirmBudget"
              type="number"
              min="0"
              step="0.01"
              class="mt-1 w-full rounded border border-white/10 bg-zinc-900 p-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-300"
            />
          </label>
          <p v-if="confirmError" class="mt-2 text-xs text-rose-200" role="alert">{{ confirmError }}</p>
          <div class="mt-4 flex justify-end gap-2">
            <button type="button" class="rounded-md border border-white/10 px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-zinc-300" @click="closePaidConfirm">
              {{ copy.paidConfirmCancel }}
            </button>
            <button type="submit" class="rounded-md border border-amber-300/50 bg-amber-300/10 px-3 py-1.5 text-sm font-medium text-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-300">
              {{ copy.paidConfirmSubmit }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import {
  AUTO_REPAIR_COPY as copy,
  autoRepairStatusLabel,
  autoRepairTypeLabel,
  formatRepairCost,
  safeAutoRepairText,
} from '../../constants/autoRepairCopy.js'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  busyId: { type: String, default: '' },
  initialVisibleCount: { type: Number, default: 5 },
})

const emit = defineEmits(['retry', 'manual-action'])

const expanded = ref(false)
const confirmTask = ref(null)
const confirmReason = ref('')
const confirmBudget = ref(0)
const confirmError = ref('')
const reasonInput = ref(null)
const lastTrigger = ref(null)
const dialogTitleId = `auto-repair-paid-confirm-${Math.random().toString(36).slice(2)}`

const visibleTasks = computed(() => expanded.value ? props.tasks : props.tasks.slice(0, props.initialVisibleCount))
const hasHiddenTasks = computed(() => props.tasks.length > props.initialVisibleCount)

function text(value, fallback) {
  return safeAutoRepairText(value, fallback)
}

function typeLabel(type) {
  return autoRepairTypeLabel(type)
}

function statusLabel(status) {
  return autoRepairStatusLabel(status)
}

function canRetry(task) {
  return Boolean(task?.retry_actions?.retry_enabled || task?.retry_actions?.paid_authorization_required)
}

function primaryLabel(task) {
  return safeAutoRepairText(task?.retry_actions?.primary_label, task?.retry_actions?.paid_authorization_required ? copy.authorizeRetry : copy.retry)
}

function affectedTextFor(task) {
  return (task.affected_ids || []).filter(Boolean).join('、')
}

async function handleRetry(task) {
  if (task?.retry_actions?.paid_authorization_required) {
    lastTrigger.value = document.activeElement
    confirmTask.value = task
    confirmReason.value = ''
    confirmBudget.value = Number(task.estimated_cost || 0)
    confirmError.value = ''
    await nextTick()
    reasonInput.value?.focus()
    return
  }
  emit('retry', task)
}

function closePaidConfirm() {
  confirmTask.value = null
  confirmError.value = ''
  const trigger = lastTrigger.value
  lastTrigger.value = null
  trigger?.focus?.()
}

function confirmPaidRetry() {
  if (!confirmReason.value.trim()) {
    confirmError.value = copy.paidConfirmMissingReason
    return
  }
  const task = confirmTask.value
  const payload = {
    reason: confirmReason.value.trim(),
    budget_delta: Number(confirmBudget.value || 0),
    confirmed_budget_delta: Number(confirmBudget.value || 0),
  }
  closePaidConfirm()
  emit('retry', task, payload)
}
</script>
