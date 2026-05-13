<template>
  <div class="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
    <div class="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
      <span class="text-xs font-medium text-gray-400 font-mono">Prompt Debugger</span>
      <span class="text-xs text-gray-500">{{ props.entries?.length || 0 }} entries</span>
    </div>
    <div class="divide-y divide-gray-800 max-h-96 overflow-y-auto">
      <div v-for="(entry, i) in props.entries" :key="i" class="p-3">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xs text-gray-500 font-mono">{{ entry.timestamp }}</span>
          <span class="px-1.5 py-0.5 rounded text-xs font-medium"
                :class="typeColor(entry.type)">{{ entry.type }}</span>
          <span class="text-xs text-gray-500">{{ entry.model }}</span>
        </div>
        <div class="text-xs text-gray-300 font-mono whitespace-pre-wrap bg-gray-800 rounded p-2 mt-1">
          {{ entry.prompt?.slice(0, 500) }}{{ entry.prompt?.length > 500 ? '...' : '' }}
        </div>
        <div v-if="entry.response" class="text-xs text-green-400 font-mono mt-1 bg-gray-800 rounded p-2">
          {{ entry.response?.slice(0, 300) }}{{ entry.response?.length > 300 ? '...' : '' }}
        </div>
      </div>
      <div v-if="!props.entries || props.entries.length === 0"
           class="p-6 text-center text-xs text-gray-600">暂无 AI 调用记录</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  entries: { type: Array, default: () => [] },
})

function typeColor(t) {
  return { llm: 'bg-blue-900 text-blue-300', render: 'bg-purple-900 text-purple-300',
           audit: 'bg-green-900 text-green-300', tts: 'bg-yellow-900 text-yellow-300',
           image: 'bg-orange-900 text-orange-300' }[t] || 'bg-gray-800 text-gray-400'
}
</script>
