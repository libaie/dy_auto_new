<template>
  <div class="p-6">
    <button @click="$router.push('/series')" class="text-sky-400 hover:text-sky-300 mb-4 transition cursor-pointer">&larr; 返回系列列表</button>
    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <template v-else-if="series">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-slate-100">{{ series.title }}</h1>
          <p class="text-slate-400 mt-1">{{ series.logline }}</p>
          <div class="flex gap-3 mt-2 text-sm text-slate-500">
            <span>{{ series.total_episodes }} 集</span><span>{{ series.genre }}</span>
            <span>{{ series.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
          </div>
        </div>
        <button @click="startPipelineRun" :disabled="pipelineStarting"
                class="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
          {{ pipelineStarting ? '启动中...' : '▶ 启动流水线' }}
        </button>
      </div>

      <div class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px);">
        <div class="px-5 py-3 border-b border-gray-700/50 font-medium text-slate-200">剧集列表</div>
        <div class="divide-y divide-gray-700/30 max-h-[600px] overflow-y-auto">
          <div v-for="ep in episodes" :key="ep.id" class="px-5 py-3 flex items-center gap-4 hover:bg-gray-800/40 transition cursor-pointer">
            <span class="text-slate-500 w-12 text-sm">E{{ String(ep.episode_number).padStart(2, '0') }}</span>
            <span class="flex-1 text-sm text-slate-200">{{ ep.title || '未命名' }}</span>
            <span class="text-xs text-slate-500 w-16 text-right">{{ ep.duration_seconds ? ep.duration_seconds + 's' : '-' }}</span>
            <span :class="epStatusClass(ep.status)" class="px-2 py-1 rounded text-xs">{{ ep.status }}</span>
          </div>
        </div>
      </div>

      <div v-if="runs.length" class="mt-8">
        <h2 class="text-lg font-semibold text-slate-100 mb-3">流水线运行历史</h2>
        <div class="space-y-2">
          <div v-for="r in runs" :key="r.id" @click="$router.push(`/pipeline/${r.id}`)"
               class="rounded-lg border border-gray-700/50 px-4 py-3 flex items-center gap-4 hover:shadow-lg hover:shadow-sky-900/10 transition cursor-pointer"
               style="background: rgba(15, 23, 42, 0.5);">
            <span class="text-xs text-slate-500 font-mono">{{ r.id.slice(0, 8) }}</span>
            <span :class="runStatusClass(r.status)" class="px-2 py-1 rounded text-xs">{{ r.status }}</span>
            <span class="text-xs text-slate-500">Layer {{ r.current_layer }}/6</span>
            <span class="text-xs text-slate-500 ml-auto">{{ r.created_at?.slice(0, 19) }}</span>
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
const route = useRoute(); const series = ref(null); const episodes = ref([]); const runs = ref([]); const loading = ref(true); const pipelineStarting = ref(false); const error = ref('')
async function load() { loading.value = true; error.value = ''; try { const { data } = await getSeries(route.params.id); if (data.ok) { series.value = data.series; episodes.value = data.episodes || [] } else throw new Error('Series not found'); const r = await listRuns(route.params.id); runs.value = r.data.ok ? r.data.runs : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function startPipelineRun() { pipelineStarting.value = true; try { await startPipeline(route.params.id, null, series.value.mode) } catch (e) { error.value = e.message || '启动失败' } finally { pipelineStarting.value = false }; await load() }
function epStatusClass(s) { return { pending: 'bg-gray-800 text-slate-400', rendering: 'bg-yellow-900/40 text-yellow-400', done: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400' }[s] || 'bg-gray-800 text-slate-400' }
function runStatusClass(s) { return { running: 'bg-sky-900/40 text-sky-400', completed: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400', pending: 'bg-gray-800 text-slate-400' }[s] || 'bg-gray-800 text-slate-400' }
onMounted(load)
</script>
