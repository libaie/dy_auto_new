<template>
  <div class="p-6">
    <button @click="$router.back()" class="text-sky-400 hover:text-sky-300 mb-4 transition cursor-pointer">&larr; 返回</button>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <template v-else-if="run">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-slate-100">流水线监控</h1>
          <p class="text-slate-500 text-sm font-mono mt-1">Run {{ run.id.slice(0, 8) }}</p>
        </div>
        <span :class="runStatusClass(run.status)" class="px-3 py-1 rounded-lg text-sm font-medium">{{ run.status }}</span>
      </div>

      <div class="space-y-2 mb-6">
        <div v-for="(layer, idx) in layers" :key="idx" class="flex items-center gap-4">
          <span class="w-8 text-center text-lg text-slate-300">{{ idx }}</span>
          <span class="w-24 text-sm text-slate-400">{{ layerNames[idx] }}</span>
          <div class="flex-1 rounded-full h-2.5" style="background: rgba(255,255,255,0.06);">
            <div :class="layerBarClass(layer.status)" class="h-2.5 rounded-full transition-all duration-500"
                 :style="{ width: layer.status === 'completed' ? '100%' : layer.status === 'running' ? '60%' : '0%' }"></div>
          </div>
          <span class="w-16 text-xs text-right" :class="layer.status === 'completed' ? 'text-emerald-400' : 'text-slate-500'">
            {{ layer.status === 'completed' ? '✓ 完成' : layer.status === 'running' ? '进行中' : '—' }}
          </span>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-4 mb-6">
        <div v-for="stat in stats" :key="stat.label" class="rounded-xl border border-gray-700/50 p-4 text-center" style="background: rgba(15, 23, 42, 0.5);">
          <div class="text-2xl font-bold text-slate-100">{{ stat.value }}</div>
          <div class="text-xs text-slate-500 mt-1">{{ stat.label }}</div>
        </div>
      </div>

      <div v-if="run.error_log" class="rounded-xl border border-red-800/50 p-4 text-sm text-red-400" style="background: rgba(127, 29, 29, 0.1);">
        <strong>错误：</strong> {{ run.error_log }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getRun } from '../api/pipeline.js'
const route = useRoute(); const run = ref(null); const loading = ref(true); const error = ref(''); let timer = null
const layerNames = ['资产生成', '资产工坊', '故事工坊', '导演工坊', '渲染引擎', '后期包装']
const layers = computed(() => { if (!run.value) return []; const json = run.value.layers_json || {}; return Array.from({ length: 6 }, (_, i) => ({ status: json[String(i)]?.status || (i === run.value.current_layer ? 'running' : 'pending') })) })
const stats = computed(() => { if (!run.value) return []; const diff = run.value.started_at ? Math.floor((Date.now() - new Date(run.value.started_at).getTime()) / 1000) : 0; return [{ label: '当前层', value: `${run.value.current_layer}/6` }, { label: '累计成本', value: `¥${(run.value.actual_cost_so_far || 0).toFixed(2)}` }, { label: '运行时间', value: `${Math.floor(diff/60)}m ${diff%60}s` }] })
async function load() { try { const { data } = await getRun('_', route.params.runId); if (data.ok) run.value = data.run; else throw new Error('Not found') } catch (e) { error.value = e.message || '加载失败'; if (timer) clearInterval(timer) } finally { loading.value = false } }
function runStatusClass(s) { return { running: 'bg-sky-900/40 text-sky-400', completed: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400', pending: 'bg-gray-800 text-slate-400' }[s] || 'bg-gray-800 text-slate-400' }
function layerBarClass(s) { return s === 'completed' ? 'bg-emerald-500' : s === 'running' ? 'bg-sky-500 animate-pulse' : '' }
onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>
