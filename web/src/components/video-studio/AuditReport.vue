<template>
  <div class="bg-white rounded-xl border overflow-hidden">
    <div class="px-4 py-3 border-b font-medium text-sm text-gray-700 flex items-center justify-between">
      <span>审图报告</span>
      <span :class="scoreColor(props.score)" class="text-lg font-bold">{{ props.score.toFixed(0) }}</span>
    </div>
    <div class="p-4 space-y-2 max-h-64 overflow-y-auto">
      <div v-if="!props.issues || props.issues.length === 0" class="text-xs text-green-600 flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
        未发现问题
      </div>
      <div v-for="(issue, i) in props.issues" :key="i"
           class="flex items-start gap-2 text-xs p-2 rounded-lg"
           :class="issue.severity === 'critical' ? 'bg-red-50 text-red-700' : 'bg-yellow-50 text-yellow-700'">
        <span class="mt-0.5">{{ issue.severity === 'critical' ? '!' : '?' }}</span>
        <span>{{ issue.description }}</span>
      </div>
    </div>
    <div class="px-4 py-2 border-t text-xs text-gray-400 flex justify-between">
      <span>{{ props.auditor_model }}</span>
      <span :class="props.pass_fail ? 'text-green-600' : 'text-red-600'">
        {{ props.pass_fail ? 'PASS' : 'FAIL' }}
      </span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  score: { type: Number, default: 0 },
  pass_fail: { type: Boolean, default: false },
  issues: { type: Array, default: () => [] },
  auditor_model: { type: String, default: 'gemini-2.5-pro' },
})

function scoreColor(s) {
  if (s >= 85) return 'text-green-600'
  if (s >= 70) return 'text-yellow-600'
  return 'text-red-600'
}
</script>
