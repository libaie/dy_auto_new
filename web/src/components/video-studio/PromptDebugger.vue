<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<template>
  <div class="rounded-xl border border-gray-700 overflow-hidden" style="background: rgba(2, 6, 23, 0.9);">
    <div class="px-4 py-2 border-b border-gray-700/50 flex items-center justify-between">
      <span class="text-xs font-medium text-slate-400 font-mono">Prompt Debugger</span>
      <span class="text-xs text-slate-500">{{ props.entries?.length || 0 }} entries</span>
    </div>
    <div class="divide-y divide-gray-800 max-h-96 overflow-y-auto">
      <div v-for="(entry, i) in props.entries" :key="i" class="p-3">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xs text-slate-500 font-mono">{{ entry.timestamp }}</span>
          <span class="px-1.5 py-0.5 rounded text-xs font-medium" :class="typeColor(entry.type)">{{ entry.type }}</span>
          <span class="text-xs text-slate-500">{{ entry.model }}</span>
        </div>
        <div class="text-xs text-slate-300 font-mono whitespace-pre-wrap rounded p-2 mt-1" style="background: rgba(255,255,255,0.04);">
          {{ entry.prompt?.slice(0, 500) }}{{ entry.prompt?.length > 500 ? '...' : '' }}
        </div>
        <div v-if="entry.response" class="text-xs text-emerald-400 font-mono mt-1 rounded p-2" style="background: rgba(16, 185, 129, 0.06);">
          {{ entry.response?.slice(0, 300) }}{{ entry.response?.length > 300 ? '...' : '' }}
        </div>
      </div>
      <div v-if="!props.entries || props.entries.length === 0" class="p-6 text-center text-xs text-slate-600">暂无 AI 调用记录</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ entries: { type: Array, default: () => [] } })
// 前端业务函数：协调 typeColor 对应的页面流程、接口调用或状态转换。
function typeColor(t) { return { llm: 'bg-sky-900/40 text-sky-400', render: 'bg-purple-900/40 text-purple-400', audit: 'bg-emerald-900/40 text-emerald-400', tts: 'bg-yellow-900/40 text-yellow-400', image: 'bg-orange-900/40 text-orange-400' }[t] || 'bg-gray-800 text-slate-400' }
</script>
