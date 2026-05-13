<template>
  <div class="rounded-xl border border-gray-700/50 p-4" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <h3 class="text-sm font-semibold text-slate-200 mb-3">模型路由配置</h3>
    <div class="space-y-2">
      <div v-for="m in models" :key="m.id"
           class="flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all duration-200"
           :class="props.selected === m.id ? 'ring-2 ring-sky-500/50' : 'hover:bg-gray-800/50'"
           style="background: rgba(255,255,255,0.03);"
           @click="$emit('select', m.id)">
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold" :class="providerColor(m.provider)">{{ m.name?.[0] || '?' }}</div>
        <div class="flex-1">
          <div class="text-sm font-medium text-slate-200">{{ m.name }}</div>
          <div class="text-xs text-slate-500">{{ m.provider }}</div>
        </div>
        <div v-if="props.selected === m.id" class="w-5 h-5 rounded-full bg-sky-500 flex items-center justify-center transition">
          <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ models: { type: Array, default: () => [] }, selected: { type: String, default: '' } })
defineEmits(['select'])
function providerColor(p) { return { volcengine: 'bg-purple-900/40 text-purple-400', kuaishou: 'bg-emerald-900/40 text-emerald-400', runninghub: 'bg-orange-900/40 text-orange-400' }[p] || 'bg-gray-800 text-slate-400' }
</script>
