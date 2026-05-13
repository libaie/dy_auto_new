<template>
  <div class="p-6">
    <button @click="$router.back()" class="text-blue-600 hover:underline mb-4">&larr; 返回</button>

    <div v-if="loading" class="text-gray-500 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-500 text-center py-12">{{ error }}</div>
    <template v-else-if="run">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">流水线监控</h1>
          <p class="text-gray-500 text-sm font-mono mt-1">Run {{ run.id.slice(0, 8) }}</p>
        </div>
        <span :class="runStatusClass(run.status)" class="px-3 py-1 rounded-lg text-sm font-medium">{{ run.status }}</span>
      </div>

      <!-- 七层进度 -->
      <div class="space-y-2 mb-6">
        <div v-for="(layer, idx) in layers" :key="idx" class="flex items-center gap-4">
          <span class="w-8 text-center text-lg">{{ layerIcons[idx] }}</span>
          <span class="w-24 text-sm text-gray-600">{{ layerNames[idx] }}</span>
          <div class="flex-1 bg-gray-200 rounded-full h-2.5">
            <div :class="layerBarClass(layer.status)" class="h-2.5 rounded-full transition-all duration-500"
                 :style="{ width: layer.status === 'completed' ? '100%' : layer.status === 'running' ? '60%' : '0%' }"></div>
          </div>
          <span class="w-16 text-xs text-right" :class="layer.status === 'completed' ? 'text-green-600' : 'text-gray-400'">
            {{ layer.status === 'completed' ? '✓ 完成' : layer.status === 'running' ? '进行中' : '—' }}
          </span>
        </div>
      </div>

      <!-- 统计 -->
      <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-white rounded-xl border p-4 text-center">
          <div class="text-2xl font-bold text-gray-900">{{ run.current_layer }}/6</div>
          <div class="text-xs text-gray-400 mt-1">当前层</div>
        </div>
        <div class="bg-white rounded-xl border p-4 text-center">
          <div class="text-2xl font-bold text-gray-900">¥{{ (run.actual_cost_so_far || 0).toFixed(2) }}</div>
          <div class="text-xs text-gray-400 mt-1">累计成本</div>
        </div>
        <div class="bg-white rounded-xl border p-4 text-center">
          <div class="text-2xl font-bold text-gray-900">{{ elapsed }}</div>
          <div class="text-xs text-gray-400 mt-1">运行时间</div>
        </div>
      </div>

      <!-- 错误日志 -->
      <div v-if="run.error_log" class="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
        <strong>错误：</strong> {{ run.error_log }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getRun } from '../api/pipeline.js'

const route = useRoute()
const run = ref(null)
const loading = ref(true)
let timer = null

const layerNames = ['资产生成', '资产工坊', '故事工坊', '导演工坊', '渲染引擎', '后期包装']
const layerIcons = ['⓪', '①', '②', '③', '④', '⑤']

const layers = computed(() => {
  if (!run.value) return []
  const json = run.value.layers_json || {}
  return Array.from({ length: 6 }, (_, i) => ({
    status: json[String(i)]?.status || (i === run.value.current_layer ? 'running' : 'pending')
  }))
})

const elapsed = computed(() => {
  if (!run.value?.started_at) return '-'
  const diff = Math.floor((Date.now() - new Date(run.value.started_at).getTime()) / 1000)
  const m = Math.floor(diff / 60)
  const s = diff % 60
  return `${m}m ${s}s`
})

const error = ref('')

async function load() {
  try {
    const { data } = await getRun('_', route.params.runId)
    if (data.ok) run.value = data.run
    else throw new Error('Run not found')
  } catch (e) {
    error.value = e.message || '加载失败'
    if (timer) clearInterval(timer)  // stop polling on error
  } finally {
    loading.value = false
  }
}

function runStatusClass(s) {
  return { running: 'bg-blue-100 text-blue-700', completed: 'bg-green-100 text-green-700',
           failed: 'bg-red-100 text-red-700', pending: 'bg-gray-100' }[s] || 'bg-gray-100'
}
function layerBarClass(s) {
  return s === 'completed' ? 'bg-green-500' : s === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-gray-200'
}

onMounted(() => {
  load()
  timer = setInterval(load, 5000)
})
onUnmounted(() => clearInterval(timer))
</script>
