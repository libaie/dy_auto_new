<script setup>
import { ref, onMounted } from 'vue'
import { getModelOptions } from '../../api/aiConfig.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue'])

function setLayer(layer, value) {
  emit('update:modelValue', { ...props.modelValue, [layer]: value })
}

const layers = [
  { key: 'scriptLLM', label: '脚本生成', modelType: 'llm', color: 'sky',
    icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { key: 'imageModel', label: '画面生成', modelType: 'image', color: 'emerald',
    icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { key: 'videoModel', label: '视频渲染', modelType: 'video', color: 'purple',
    icon: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'ttsModel', label: '语音合成', modelType: 'tts', color: 'amber',
    icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z' },
  { key: 'auditModel', label: '质量审计', modelType: 'audit', color: 'rose',
    icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
]

const colorMap = {
  sky: { active: 'bg-sky-500/15 text-sky-300 border-sky-500/30', dot: 'bg-sky-400' },
  emerald: { active: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
  purple: { active: 'bg-purple-500/15 text-purple-300 border-purple-500/30', dot: 'bg-purple-400' },
  amber: { active: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
  rose: { active: 'bg-rose-500/15 text-rose-300 border-rose-500/30', dot: 'bg-rose-400' },
}

const modelOptions = ref({})
const loading = ref(true)

onMounted(async () => {
  try {
    const results = await Promise.all(
      layers.map(l => getModelOptions(l.modelType).catch(() => ({ data: { ok: false, options: [] } })))
    )
    layers.forEach((l, i) => {
      const data = results[i].data
      modelOptions.value[l.key] = data.ok ? data.options : []
    })
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="rounded-xl border border-gray-700/50 p-4" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <h3 class="text-xs font-medium text-slate-400 mb-3 flex items-center gap-2">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/></svg>
      各环节模型配置
      <span v-if="loading" class="text-slate-600 text-[10px]">加载中...</span>
      <span v-else class="text-slate-600 text-[10px]">— 在系统字典中管理</span>
    </h3>
    <div class="grid grid-cols-5 gap-3">
      <div v-for="layer in layers" :key="layer.key" class="relative">
        <div class="flex items-center gap-1.5 mb-2">
          <div class="w-5 h-5 rounded flex items-center justify-center" :class="colorMap[layer.color].dot" style="--tw-bg-opacity: 0.2;">
            <svg class="w-3 h-3" :class="colorMap[layer.color].dot.replace('bg-', 'text-')" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="layer.icon"/>
            </svg>
          </div>
          <span class="text-xs font-medium text-slate-300">{{ layer.label }}</span>
        </div>

        <div v-if="loading" class="w-full rounded-lg px-2.5 py-2 text-xs bg-gray-800/30 border border-gray-700/30 text-slate-600 animate-pulse">加载中...</div>

        <select
          v-else
          :value="modelValue[layer.key]"
          @change="setLayer(layer.key, $event.target.value)"
          class="layer-select w-full rounded-lg px-2.5 py-2 text-xs bg-gray-800/80 border border-gray-600 text-slate-100 cursor-pointer focus:outline-none focus:ring-2 transition appearance-none"
          :class="`focus:ring-${layer.color}-500/50`"
        >
          <option v-for="opt in (modelOptions[layer.key] || [])" :key="opt.id" :value="opt.id">{{ opt.name }}</option>
        </select>

        <p class="text-[10px] text-slate-500 mt-1 leading-tight truncate">
          {{ ((modelOptions[layer.key] || []).find(o => o.id === modelValue[layer.key]) || {}).provider || '' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3E%3C/svg%3E");
  background-position: right 0.25rem center;
  background-repeat: no-repeat;
  background-size: 1.25em;
}
</style>
