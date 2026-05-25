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
            <span :class="styleLock?.locked ? 'text-emerald-400' : 'text-amber-400'">
              {{ styleLock?.locked ? `风格已锁定 v${styleLock.version || 1}` : '风格未锁定' }}
            </span>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="lockStyle" :disabled="styleLocking"
                  class="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ styleLocking ? '锁定中...' : (styleLock?.locked ? '重新锁定风格' : '锁定风格') }}
          </button>
          <button @click="$router.push(`/series/${series.id}/agency-console`)"
                  class="bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            专家团队控制台
          </button>
          <button v-if="!series.character_count && !series.scene_count && series.logline" @click="autoGenerate"
                  :disabled="autoGenerating" class="bg-purple-500 hover:bg-purple-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer"
                  title="根据故事概要，AI 自动生成角色和场景">
            {{ autoGenerating ? 'AI 生成中...' : 'AI 一键生成角色&场景' }}
          </button>
          <button @click="startPipelineRun" :disabled="pipelineStartDisabled"
                  class="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ pipelineButtonText }}
          </button>
        </div>
      </div>

      <div v-if="styleLock" class="rounded-xl border border-gray-700/50 px-4 py-3 mb-6 text-sm text-slate-400" style="background: rgba(15, 23, 42, 0.5);">
        <div class="flex flex-wrap gap-4">
          <span>角色参考图 {{ styleLock.reference_status?.characters?.ready || 0 }}/{{ styleLock.reference_status?.characters?.total || 0 }}</span>
          <span>场景参考图 {{ styleLock.reference_status?.scenes?.ready || 0 }}/{{ styleLock.reference_status?.scenes?.total || 0 }}</span>
          <span v-if="styleLock.missing_assets?.length" class="text-amber-300">待补资产 {{ styleLock.missing_assets.length }}</span>
          <span v-if="styleLock.agency_team_status?.enabled" class="text-cyan-300">
            专家团队 {{ styleLock.agency_team_status.core_role_count || 0 }} 核心 / {{ styleLock.agency_team_status.support_role_count || 0 }} 支援
          </span>
        </div>
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

    <!-- AI 自动生成进度对话框 -->
    <div v-if="autoGenerating || autoGenResult" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="autoGenResult = null; load()">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50 max-h-[85vh] overflow-y-auto" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">AI 自动生成</h2>
        <template v-if="autoGenerating">
          <div class="text-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-3"></div>
            <p class="text-sm text-slate-400">{{ autoGenStep }}</p>
          </div>
        </template>
        <template v-else-if="autoGenResult">
          <p class="text-xs text-slate-500 mb-4">AI 已根据故事概要生成以下资产：</p>
          <div v-if="autoGenResult.characters?.length" class="mb-4">
            <h3 class="text-sm font-medium text-slate-200 mb-2">角色 ({{ autoGenResult.characters.length }})</h3>
            <div class="space-y-1">
              <div v-for="(c, i) in autoGenResult.characters" :key="'c'+i" class="text-xs text-slate-400 flex gap-2">
                <span class="text-slate-100">{{ c.name }}</span>
                <span class="text-slate-500">· {{ c.role_type }} · {{ c.gender === 'male' ? '男' : '女' }}</span>
              </div>
            </div>
          </div>
          <div v-if="autoGenResult.scenes?.length" class="mb-4">
            <h3 class="text-sm font-medium text-slate-200 mb-2">场景 ({{ autoGenResult.scenes.length }})</h3>
            <div class="space-y-1">
              <div v-for="(sc, i) in autoGenResult.scenes" :key="'s'+i" class="text-xs text-slate-400 flex gap-2">
                <span class="text-slate-100">{{ sc.name }}</span>
                <span class="text-slate-500">· {{ sc.scene_type }} · {{ sc.lighting }}</span>
              </div>
            </div>
          </div>
          <div class="flex justify-end mt-4">
            <button @click="autoGenResult = null; load()" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer text-sm">完成</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSeries, autoGenerateAssets, getStyleLock, lockSeriesStyle } from '../api/series.js'
import { autoPlanEpisode } from '../api/director.js'
import { listRuns } from '../api/pipeline.js'
import { createVideoProductionRun, startImageStage } from '../api/videoProduction.js'
const route = useRoute(); const router = useRouter(); const series = ref(null); const episodes = ref([]); const runs = ref([]); const styleLock = ref(null); const loading = ref(true); const pipelineStarting = ref(false); const styleLocking = ref(false); const error = ref('')
const autoGenerating = ref(false); const autoGenStep = ref(''); const autoGenResult = ref(null)
const runnableEpisode = computed(() => episodes.value.find(ep => !['done', 'rendering'].includes(ep.status)) || null)
const pipelineStartDisabled = computed(() => pipelineStarting.value || !runnableEpisode.value)
const pipelineButtonText = computed(() => {
  if (pipelineStarting.value) return '启动中...'
  if (!episodes.value.length) return '没有可启动剧集'
  if (!runnableEpisode.value) return '全部剧集已完成'
  return '▶ 启动下一集流水线'
})
async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await getSeries(route.params.id)
    if (data.ok) { series.value = data.series; episodes.value = data.episodes || [] } else throw new Error('Series not found')
    const [runsResp, styleResp] = await Promise.all([
      listRuns(route.params.id),
      getStyleLock(route.params.id).catch(() => ({ data: null })),
    ])
    runs.value = runsResp.data.ok ? runsResp.data.runs : []
    styleLock.value = styleResp.data
  } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false }
}
function nextEpisode() {
  return runnableEpisode.value
}
async function lockStyle(rethrow = false) {
  const shouldRethrow = rethrow === true
  styleLocking.value = true; error.value = ''
  try {
    const { data } = await lockSeriesStyle(route.params.id)
    styleLock.value = { ...data, locked: true, version: data.story_bible?.style_lock?.version || 1 }
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '风格锁定失败'
    if (shouldRethrow) throw e
  } finally { styleLocking.value = false }
}
async function startPipelineRun() {
  pipelineStarting.value = true; error.value = ''
  try {
    if (!styleLock.value?.locked) await lockStyle(true)
    const ep = nextEpisode()
    if (!ep) throw new Error('没有可启动的剧集')
    await autoPlanEpisode(route.params.id, ep.id, series.value.target_duration)
    const { data } = await createVideoProductionRun(route.params.id, ep.id)
    if (!data?.run?.id) throw new Error('Production run was not created')
    await startImageStage(data.run.id)
    router.push(`/video-production/${data.run.id}`)
  } catch (e) { error.value = e.response?.data?.detail || e.message || '启动失败' } finally { pipelineStarting.value = false }
}
async function autoGenerate() {
  autoGenerating.value = true; autoGenResult.value = null; error.value = ''
  try {
    autoGenStep.value = 'AI 正在分析故事，生成角色档案...'
    const { data } = await autoGenerateAssets(route.params.id)
    if (data.ok) {
      autoGenResult.value = data
      autoGenStep.value = ''
      await load()
    } else throw new Error('生成失败')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'AI 生成失败'
    autoGenerating.value = false
  } finally { autoGenerating.value = false }
}
function epStatusClass(s) { return { pending: 'bg-gray-800 text-slate-400', rendering: 'bg-yellow-900/40 text-yellow-400', done: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400' }[s] || 'bg-gray-800 text-slate-400' }
function runStatusClass(s) { return { running: 'bg-sky-900/40 text-sky-400', completed: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400', pending: 'bg-gray-800 text-slate-400' }[s] || 'bg-gray-800 text-slate-400' }
onMounted(load)
</script>
