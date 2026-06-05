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
          <button data-test="edit-series" @click="beginEditSeries"
                  class="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            编辑系列
          </button>
          <button data-test="lock-style" @click="lockStyle" :disabled="styleLockInProgress"
                  class="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ styleLockInProgress ? '锁定中...' : (styleLock?.locked ? '重新锁定风格' : '锁定风格') }}
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
          <button data-test="start-pipeline" @click="startPipelineRun" :disabled="pipelineStartDisabled"
                  class="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ pipelineButtonText }}
          </button>
          <button @click="deleteDialogOpen = true"
                  class="border border-red-500/40 bg-red-500/10 hover:bg-red-500/20 text-red-300 px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            安全归档
          </button>
        </div>
      </div>

      <div v-if="editingSeries" class="mb-6 rounded-xl border border-slate-700 bg-slate-950/50 p-4">
        <div v-if="saveError" class="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {{ saveError }}
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">标题</span>
            <input data-test="series-title-input" v-model="seriesForm.title" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">类型</span>
            <input v-model="seriesForm.genre" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">目标时长</span>
            <input v-model.number="seriesForm.target_duration" type="number" min="1" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
          </label>
          <label class="block text-sm text-slate-300">
            <span class="mb-1 block">制作模式</span>
            <select v-model="seriesForm.mode" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700">
              <option value="fully_automatic">全自动</option>
              <option value="step_by_step">逐步确认</option>
            </select>
          </label>
        </div>
        <label class="mt-3 block text-sm text-slate-300">
          <span class="mb-1 block">故事梗概</span>
          <textarea v-model="seriesForm.logline" rows="3" class="w-full rounded bg-slate-900 px-3 py-2 text-slate-100 border border-slate-700" />
        </label>
        <label class="mt-3 flex items-center gap-2 text-sm text-slate-300">
          <input v-model="seriesForm.pilot_first" type="checkbox" class="rounded border-slate-600 bg-slate-900" />
          <span>先制作试播集</span>
        </label>
        <div class="mt-4 flex justify-end gap-2">
          <button @click="editingSeries = false" class="rounded border border-slate-700 px-4 py-2 text-sm text-slate-300">取消</button>
          <button data-test="save-series" @click="saveSeries" :disabled="savingSeries"
                  class="rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-50">
            {{ savingSeries ? '保存中...' : '保存系列' }}
          </button>
        </div>
      </div>

      <div v-if="deleteResult" class="mb-6 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">
        {{ deleteResult }}
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

      <div class="grid gap-4 lg:grid-cols-2 mb-6">
        <section class="rounded-xl border border-slate-700 bg-slate-950/50 p-4">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-slate-100">关联角色</h2>
            <span class="text-xs text-slate-500">{{ (series.characters || []).length }} 个</span>
          </div>
          <div v-if="unlinkErrors.character" class="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {{ unlinkErrors.character }}
          </div>
          <div v-if="!(series.characters || []).length" class="text-sm text-slate-500">尚未关联角色</div>
          <div v-for="character in series.characters || []" :key="character.id" class="mb-2 flex items-center justify-between gap-3 rounded bg-slate-900/60 p-3">
            <div class="flex min-w-0 items-center gap-3">
              <a v-if="safeReferenceUrl(character.avatar_front_url)" :href="safeReferenceUrl(character.avatar_front_url)" target="_blank" rel="noreferrer" class="block h-12 w-12 shrink-0 overflow-hidden rounded border border-slate-700">
                <img :src="safeReferenceUrl(character.avatar_front_url)" :alt="`${character.name} 正面参考图`" class="h-full w-full object-cover" />
              </a>
              <div v-else class="flex h-12 w-12 shrink-0 items-center justify-center rounded border border-slate-700 text-xs text-slate-500">
                {{ character.avatar_front_url ? '链接无效' : '待生成' }}
              </div>
              <div class="min-w-0">
                <div class="truncate text-sm text-slate-100">{{ character.name }}</div>
                <div class="text-xs text-slate-500">{{ character.role_type }}</div>
                <a v-if="safeReferenceUrl(character.avatar_front_url)" :href="safeReferenceUrl(character.avatar_front_url)" target="_blank" rel="noreferrer" class="text-xs text-cyan-300 hover:text-cyan-200">查看正面参考图</a>
                <span v-else-if="character.avatar_front_url" class="text-xs text-red-300">链接无效</span>
              </div>
            </div>
            <button :data-test="`unlink-character-${character.id}`" class="shrink-0 rounded border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800" @click="removeCharacter(character.id)">
              取消关联
            </button>
          </div>
        </section>

        <section class="rounded-xl border border-slate-700 bg-slate-950/50 p-4">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-slate-100">关联场景</h2>
            <span class="text-xs text-slate-500">{{ (series.scenes || []).length }} 个</span>
          </div>
          <div v-if="unlinkErrors.scene" class="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {{ unlinkErrors.scene }}
          </div>
          <div v-if="!(series.scenes || []).length" class="text-sm text-slate-500">尚未关联场景</div>
          <div v-for="scene in series.scenes || []" :key="scene.id" class="mb-2 flex items-center justify-between gap-3 rounded bg-slate-900/60 p-3">
            <div class="flex min-w-0 items-center gap-3">
              <a v-if="safeReferenceUrl(scene.reference_wideshot_url)" :href="safeReferenceUrl(scene.reference_wideshot_url)" target="_blank" rel="noreferrer" class="block h-12 w-12 shrink-0 overflow-hidden rounded border border-slate-700">
                <img :src="safeReferenceUrl(scene.reference_wideshot_url)" :alt="`${scene.name} 广角参考图`" class="h-full w-full object-cover" />
              </a>
              <div v-else class="flex h-12 w-12 shrink-0 items-center justify-center rounded border border-slate-700 text-xs text-slate-500">
                {{ scene.reference_wideshot_url ? '链接无效' : '待生成' }}
              </div>
              <div class="min-w-0">
                <div class="truncate text-sm text-slate-100">{{ scene.name }}</div>
                <div class="text-xs text-slate-500">{{ scene.scene_type }}</div>
                <a v-if="safeReferenceUrl(scene.reference_wideshot_url)" :href="safeReferenceUrl(scene.reference_wideshot_url)" target="_blank" rel="noreferrer" class="text-xs text-cyan-300 hover:text-cyan-200">查看广角参考图</a>
                <span v-else-if="scene.reference_wideshot_url" class="text-xs text-red-300">链接无效</span>
              </div>
            </div>
            <button :data-test="`unlink-scene-${scene.id}`" class="shrink-0 rounded border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800" @click="removeScene(scene.id)">
              取消关联
            </button>
          </div>
        </section>
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

    <DangerConfirmDialog
      :open="deleteDialogOpen"
      title="确认安全归档"
      message="系统会根据后端判断执行归档或删除，并保留已有生产记录。"
      :impact="deleteError || '不会从前端直接清理生产素材。'"
      :confirm-text="deletingSeries ? '处理中...' : '确认执行'"
      @cancel="deleteDialogOpen = false"
      @confirm="removeSeries"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSeries, autoGenerateAssets, getStyleLock, lockSeriesStyle, updateSeries, deleteSeries, unlinkCharacter, unlinkScene } from '../api/series.js'
import { listRuns } from '../api/pipeline.js'
import { startEpisodeProduction } from '../api/videoProduction.js'
import DangerConfirmDialog from '../components/assets/DangerConfirmDialog.vue'
const route = useRoute(); const router = useRouter(); const series = ref(null); const episodes = ref([]); const runs = ref([]); const styleLock = ref(null); const loading = ref(true); const pipelineStarting = ref(false); const styleLocking = ref(false); const error = ref('')
const autoGenerating = ref(false); const autoGenStep = ref(''); const autoGenResult = ref(null)
const editingSeries = ref(false); const savingSeries = ref(false); const saveError = ref('')
const seriesForm = reactive({ title: '', logline: '', genre: '', target_duration: 60, mode: 'step_by_step', pilot_first: true })
const unlinkErrors = reactive({ character: '', scene: '' })
const deleteDialogOpen = ref(false); const deletingSeries = ref(false); const deleteError = ref(''); const deleteResult = ref('')
const styleLockPollTimer = ref(null)
const autostartRequested = ref(route.query?.autostart === 'production')
const autostartRunning = ref(false)
const finishedEpisodeStatuses = new Set(['done', 'completed', 'rendering'])
const activeVideoRunStatuses = new Set([
  'draft',
  'storyboard_ready',
  'image_batch_running',
  'image_generation',
  'image_review_pending',
  'image_human_review_required',
  'image_approved',
  'video_batch_running',
  'video_generation',
  'video_review_pending',
  'video_human_review_required',
  'video_segments_approved',
  'composing',
  'composition',
])
function episodeHasActiveVideoRun(ep) {
  return Boolean(ep.active_video_run_id) || activeVideoRunStatuses.has(ep.video_run_status)
}
const runnableEpisode = computed(() => episodes.value.find(ep => (
  !finishedEpisodeStatuses.has(ep.status) && !episodeHasActiveVideoRun(ep)
)) || null)
const styleLockInProgress = computed(() => styleLocking.value || styleLock.value?.status === 'locking')
const pipelineStartDisabled = computed(() => pipelineStarting.value || !runnableEpisode.value)
const pipelineButtonText = computed(() => {
  if (pipelineStarting.value) return '启动中...'
  if (!episodes.value.length) return '没有可启动剧集'
  if (!runnableEpisode.value) return '全部剧集已完成'
  return series.value?.mode === 'fully_automatic' ? '▶ 全自动生成下一集' : '▶ 创建下一集生产计划'
})
async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await getSeries(route.params.id)
    if (data.ok) { series.value = data.series; episodes.value = data.episodes || [] } else throw new Error('Series not found')
    const [runsResp, styleResp] = await Promise.all([
      listRuns(route.params.id).catch(() => ({ data: { ok: false, runs: [] } })),
      getStyleLock(route.params.id).catch(() => ({ data: null })),
    ])
    runs.value = runsResp.data.ok ? runsResp.data.runs : []
    styleLock.value = styleResp.data
    scheduleStyleLockPoll()
  } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false }
  await maybeAutostartProduction()
}
function nextEpisode() {
  return runnableEpisode.value
}
function beginEditSeries() {
  Object.assign(seriesForm, {
    title: series.value?.title || '',
    logline: series.value?.logline || '',
    genre: series.value?.genre || '',
    target_duration: series.value?.target_duration || 60,
    mode: series.value?.mode || 'step_by_step',
    pilot_first: series.value?.pilot_first ?? true,
  })
  saveError.value = ''
  editingSeries.value = true
}
function errorMessage(e, fallback) {
  const detail = e.response?.data?.detail
  return detail?.message || detail || e.message || fallback
}
function safeReferenceUrl(value) {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim()
  if (!trimmed || trimmed.startsWith('//')) return ''
  if (trimmed.startsWith('/static/') || trimmed.startsWith('/api/')) return trimmed
  try {
    const parsed = new URL(trimmed)
    return ['http:', 'https:'].includes(parsed.protocol) ? trimmed : ''
  } catch {
    return ''
  }
}
async function saveSeries() {
  savingSeries.value = true; saveError.value = ''
  try {
    await updateSeries(route.params.id, { ...seriesForm })
    editingSeries.value = false
    await load()
  } catch (e) {
    saveError.value = errorMessage(e, '保存系列失败')
  } finally { savingSeries.value = false }
}
async function removeCharacter(characterId) {
  unlinkErrors.character = ''
  try {
    await unlinkCharacter(route.params.id, characterId)
    await load()
  } catch (e) {
    unlinkErrors.character = errorMessage(e, '取消角色关联失败')
  }
}
async function removeScene(sceneId) {
  unlinkErrors.scene = ''
  try {
    await unlinkScene(route.params.id, sceneId)
    await load()
  } catch (e) {
    unlinkErrors.scene = errorMessage(e, '取消场景关联失败')
  }
}
async function removeSeries() {
  if (deletingSeries.value) return
  deletingSeries.value = true; deleteError.value = ''; deleteResult.value = ''
  try {
    const { data } = await deleteSeries(route.params.id)
    const action = data?.action || data?.result?.action || 'completed'
    deleteResult.value = `后端处理结果：${action}`
    deleteDialogOpen.value = false
    if (action === 'deleted') router.push('/series')
    else await load()
  } catch (e) {
    deleteError.value = errorMessage(e, '安全归档失败')
  } finally { deletingSeries.value = false }
}
async function lockStyle(rethrow = false) {
  if (styleLockInProgress.value) return
  const shouldRethrow = rethrow === true
  styleLocking.value = true; error.value = ''
  try {
    const { data } = await lockSeriesStyle(route.params.id)
    const lock = data.story_bible?.style_lock || {}
    styleLock.value = {
      ...data,
      locked: Boolean(lock.locked),
      status: data.status || lock.status || 'locking',
      version: lock.version || data.version || 1,
    }
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '风格锁定失败'
    if (shouldRethrow) throw e
  } finally { styleLocking.value = false }
}
async function refreshStyleLock() {
  try {
    const { data } = await getStyleLock(route.params.id)
    styleLock.value = data
    if (data?.status !== 'locking') await load()
  } catch {
    scheduleStyleLockPoll()
    return
  }
  scheduleStyleLockPoll()
}
function scheduleStyleLockPoll() {
  if (styleLockPollTimer.value) {
    clearTimeout(styleLockPollTimer.value)
    styleLockPollTimer.value = null
  }
  if (styleLock.value?.status === 'locking') {
    styleLockPollTimer.value = setTimeout(refreshStyleLock, 5000)
  }
}
onBeforeUnmount(() => {
  if (styleLockPollTimer.value) clearTimeout(styleLockPollTimer.value)
})
async function startPipelineRun() {
  pipelineStarting.value = true; error.value = ''
  try {
    if (!styleLock.value?.locked) await lockStyle(true)
    if (!styleLock.value?.locked) {
      throw new Error('风格锁定正在后台执行，请等待完成后再启动生产')
    }
    const ep = nextEpisode()
    if (!ep) throw new Error('没有可启动的剧集')
    const { data } = await startEpisodeProduction({
      series_id: route.params.id,
      episode_id: ep.id,
      target_duration_seconds: series.value?.target_duration,
      autostart_images: series.value?.mode === 'fully_automatic',
    })
    if (!data?.route) throw new Error('Production run was not created')
    router.push(data.route)
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = detail?.message || detail || e.message || '启动失败'
  } finally { pipelineStarting.value = false }
}
async function maybeAutostartProduction() {
  if (!autostartRequested.value || autostartRunning.value || pipelineStarting.value) return
  if (!series.value) return
  if (series.value.mode !== 'fully_automatic') {
    autostartRequested.value = false
    return
  }
  if (!runnableEpisode.value) {
    autostartRequested.value = false
    return
  }
  if (styleLock.value?.status === 'locking') return
  autostartRunning.value = true
  try {
    await startPipelineRun()
    if (!error.value) autostartRequested.value = false
  } finally {
    autostartRunning.value = false
  }
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
