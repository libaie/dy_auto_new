<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<template>
  <div class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <div class="px-4 py-3 border-b border-gray-700/50 font-medium text-sm text-slate-200 flex items-center justify-between">
      <span>审图报告</span><span :class="scoreColor(props.score)" class="text-lg font-bold">{{ props.score.toFixed(0) }}</span>
    </div>
    <div class="p-4 space-y-2 max-h-64 overflow-y-auto">
      <div v-if="!props.issues || props.issues.length === 0" class="text-xs text-emerald-400 flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
        未发现问题
      </div>
      <div v-for="(issue, i) in props.issues" :key="i" class="flex items-start gap-2 text-xs p-2 rounded-lg"
           :class="issue.severity === 'critical' ? 'bg-red-900/30 text-red-400' : 'bg-yellow-900/30 text-yellow-400'">
        <span class="mt-0.5">{{ issue.severity === 'critical' ? '!' : '?' }}</span>
        <span>{{ issue.description }}</span>
      </div>
    </div>
    <div class="px-4 py-2 border-t border-gray-700/50 text-xs text-slate-500 flex justify-between">
      <span>{{ props.auditor_model }}</span>
      <span :class="props.pass_fail ? 'text-emerald-400' : 'text-red-400'">{{ props.pass_fail ? 'PASS' : 'FAIL' }}</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ score: { type: Number, default: 0 }, pass_fail: { type: Boolean, default: false }, issues: { type: Array, default: () => [] }, auditor_model: { type: String, default: 'gemini-2.5-pro' } })
function scoreColor(s) { if (s >= 85) return 'text-emerald-400'; if (s >= 70) return 'text-yellow-400'; return 'text-red-400' }
</script>
