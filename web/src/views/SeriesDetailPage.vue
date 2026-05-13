<template>
  <div class="p-6">
    <button @click="$router.push('/series')" class="text-blue-600 hover:underline mb-4">&larr; 返回系列列表</button>

    <div v-if="loading" class="text-gray-500 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-500 text-center py-12">{{ error }}</div>
    <template v-else-if="series">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">{{ series.title }}</h1>
          <p class="text-gray-500 mt-1">{{ series.logline }}</p>
          <div class="flex gap-3 mt-2 text-sm text-gray-400">
            <span>{{ series.total_episodes }} 集</span>
            <span>{{ series.genre }}</span>
            <span>{{ series.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="startPipelineRun" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm"
                  :disabled="pipelineStarting">
            {{ pipelineStarting ? '启动中...' : '▶ 启动流水线' }}
          </button>
        </div>
      </div>

      <!-- 剧集列表 -->
      <div class="bg-white rounded-xl border">
        <div class="px-5 py-3 border-b font-medium text-gray-700">剧集列表</div>
        <div class="divide-y max-h-[600px] overflow-y-auto">
          <div v-for="ep in episodes" :key="ep.id"
               class="px-5 py-3 flex items-center gap-4 hover:bg-gray-50">
            <span class="text-gray-400 w-12 text-sm">E{{ String(ep.episode_number).padStart(2, '0') }}</span>
            <span class="flex-1 text-sm">{{ ep.title || '未命名' }}</span>
            <span class="text-xs text-gray-400 w-16 text-right">{{ ep.duration_seconds ? ep.duration_seconds + 's' : '-' }}</span>
            <span :class="epStatusClass(ep.status)" class="px-2 py-1 rounded text-xs">{{ ep.status }}</span>
          </div>
        </div>
      </div>

      <!-- 流水线运行历史 -->
      <div v-if="runs.length" class="mt-8">
        <h2 class="text-lg font-semibold mb-3">流水线运行历史</h2>
        <div class="space-y-2">
          <div v-for="r in runs" :key="r.id"
               @click="$router.push(`/pipeline/${r.id}`)"
               class="bg-white rounded-lg border px-4 py-3 flex items-center gap-4 hover:shadow cursor-pointer">
            <span class="text-xs text-gray-400 font-mono">{{ r.id.slice(0, 8) }}</span>
            <span :class="runStatusClass(r.status)" class="px-2 py-1 rounded text-xs">{{ r.status }}</span>
            <span class="text-xs text-gray-400">Layer {{ r.current_layer }}/6</span>
            <span class="text-xs text-gray-400 ml-auto">{{ r.created_at?.slice(0, 19) }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getSeries } from '../api/series.js'
import { startPipeline, listRuns } from '../api/pipeline.js'

const route = useRoute()
const series = ref(null)
const episodes = ref([])
const runs = ref([])
const loading = ref(true)
const pipelineStarting = ref(false)
const error = ref('')

async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await getSeries(route.params.id)
    if (data.ok) { series.value = data.series; episodes.value = data.episodes || [] }
    else throw new Error('Series not found')
    const r = await listRuns(route.params.id)
    runs.value = r.data.ok ? r.data.runs : []
  } catch (e) { error.value = e.message || '加载失败' }
  finally { loading.value = false }
}

async function startPipelineRun() {
  pipelineStarting.value = true
  try { await startPipeline(route.params.id, null, series.value.mode) }
  catch (e) { error.value = e.message || '启动失败' }
  finally { pipelineStarting.value = false }
  await load()
}

function epStatusClass(s) {
  return { pending: 'bg-gray-100 text-gray-500', rendering: 'bg-yellow-100 text-yellow-700',
           done: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700' }[s] || 'bg-gray-100'
}
function runStatusClass(s) {
  return { pending: 'bg-gray-100', running: 'bg-blue-100 text-blue-700',
           completed: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700' }[s] || 'bg-gray-100'
}

onMounted(load)
</script>
