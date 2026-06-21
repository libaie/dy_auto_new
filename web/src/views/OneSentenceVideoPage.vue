<!-- 管理端业务页面：承载 OneSentenceVideoPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="min-h-full bg-slate-950 text-slate-100">
    <div class="mx-auto max-w-6xl px-6 py-6">
      <header class="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold">一句话成片</h1>
          <p class="mt-1 text-sm text-slate-400">
            输入一个视频想法后，系统会自动创建系列、锁定风格、生成分镜，并进入可审查的生产流程。
          </p>
        </div>
        <button
          v-if="result?.route"
          type="button"
          class="rounded bg-sky-600 px-4 py-2 text-sm text-white hover:bg-sky-500"
          @click="$router.push(result.route)"
        >
          打开生产监控
        </button>
      </header>

      <section class="mb-5 border border-slate-800 bg-slate-950/70 p-5">
        <div class="mb-5">
          <div class="mb-2 text-sm font-medium text-slate-300">生产模式</div>
          <div class="flex flex-wrap gap-2" role="group" aria-label="生产模式">
            <button
              type="button"
              data-test="mode-real-short"
              class="rounded border px-4 py-2 text-sm"
              :class="mode === 'real_short_e2e' ? 'border-emerald-500 bg-emerald-950/50 text-emerald-100' : 'border-slate-700 bg-slate-900 text-slate-300'"
              @click="setMode('real_short_e2e')"
            >
              真实短片
            </button>
            <button
              type="button"
              data-test="mode-mock-series-scale"
              class="rounded border px-4 py-2 text-sm"
              :class="mode === 'mock_series_scale' ? 'border-sky-500 bg-sky-950/50 text-sky-100' : 'border-slate-700 bg-slate-900 text-slate-300'"
              @click="setMode('mock_series_scale')"
            >
              模拟长剧调度
            </button>
          </div>
          <p class="mt-2 text-sm text-slate-400">{{ modeHelp }}</p>
        </div>

        <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
          <div>
            <label class="mb-2 block text-sm font-medium text-slate-300">故事一句话</label>
            <textarea
              v-model="form.prompt"
              rows="5"
              class="w-full border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-slate-100 outline-none focus:border-sky-500"
              placeholder="例如：一位普通中年人用真实生活方式管理血糖，每集解决一个日常控糖问题。"
            />
          </div>
          <div class="space-y-4">
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-300">标题</label>
              <input
                v-model="form.title"
                class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                placeholder="可留空"
              />
            </div>
            <div>
              <label class="mb-2 block text-sm font-medium text-slate-300">目标时长（秒）</label>
              <input
                v-model.number="form.target_duration_seconds"
                data-test="target-duration-seconds"
                type="number"
                :min="durationBounds.min"
                :max="durationBounds.max"
                class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
              />
              <p class="mt-1 text-xs text-slate-500">{{ durationHelp }}</p>
            </div>
            <div v-if="mode === 'real_short_e2e'">
              <label class="mb-2 block text-sm font-medium text-slate-300">预算上限</label>
              <input
                v-model.number="form.budget_limit"
                data-test="budget-limit"
                type="number"
                min="0.01"
                step="0.01"
                class="w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
              />
              <p class="mt-1 text-xs text-slate-500">真实短片必须设置正数预算，防止误触发付费模型。</p>
            </div>
            <label class="flex items-center gap-2 text-sm text-slate-300">
              <input v-model="form.autostart_images" type="checkbox" class="accent-sky-500" />
              创建后自动启动画面生成
            </label>
          </div>
        </div>

        <AutoRepairPolicyPanel v-model="autoRepairPolicy" class="mt-4" />

        <div class="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            data-test="submit-one-sentence"
            class="rounded bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="submitting || !form.prompt.trim()"
            @click="submit"
          >
            {{ submitting ? '启动中...' : '启动生产并应用返修策略' }}
          </button>
          <span v-if="error" class="text-sm text-rose-300">{{ error }}</span>
          <span v-if="autopilotStatus" class="text-sm text-slate-400">{{ autopilotStatus }}</span>
          <span v-if="autopilotError" class="text-sm text-amber-300">{{ autopilotError }}</span>
        </div>

        <div
          v-if="repairDetail"
          data-test="repair-detail"
          class="mt-3 border border-amber-500/40 bg-amber-950/30 p-3 text-sm text-amber-100"
        >
          <div v-if="repairDetail.message">异常结论：{{ repairDetail.message }}</div>
          <div v-if="repairDetail.repair_action" class="mt-1">建议动作：{{ repairDetail.repair_action }}</div>
          <div v-if="repairDetail.repair_route" class="mt-1 font-mono text-xs text-amber-200">
            {{ repairDetail.repair_route }}
          </div>
          <div v-if="repairAffectedIds.length" class="mt-1 text-xs text-amber-200">
            影响对象：{{ repairAffectedIds.join(', ') }}
          </div>
        </div>
      </section>

      <section class="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div class="border border-slate-800 bg-slate-950/60 p-4">
          <div class="mb-3 text-sm font-semibold text-slate-200">生产步骤</div>
          <div class="space-y-2">
            <div
              v-for="step in displaySteps"
              :key="step.key"
              class="flex items-center justify-between border px-3 py-2 text-sm"
              :class="stepClass(step.status)"
            >
              <span>{{ step.label }}</span>
              <span class="text-xs">{{ statusLabel(step.status) }}</span>
            </div>
          </div>
        </div>

        <div class="border border-slate-800 bg-slate-950/60 p-4">
          <div class="mb-3 text-sm font-semibold text-slate-200">当前结果</div>
          <div v-if="!result" class="py-10 text-center text-sm text-slate-500">
            还没有启动生产。
          </div>
          <div v-else class="grid gap-3 text-sm md:grid-cols-2">
            <div class="border border-slate-800 p-3">
              <div class="text-xs text-slate-500">系列</div>
              <div class="mt-1 text-slate-100">{{ result.series?.title }}</div>
              <div class="mt-1 font-mono text-xs text-slate-500">{{ result.series?.id }}</div>
            </div>
            <div class="border border-slate-800 p-3">
              <div class="text-xs text-slate-500">运行信息</div>
              <div class="mt-1 font-mono text-slate-100">run_type: {{ resultRunType }}</div>
              <div class="mt-1 font-mono text-slate-100">status: {{ result.run?.status }}</div>
              <div class="mt-1 font-mono text-xs text-slate-500">{{ result.run?.id }}</div>
            </div>
            <div class="border border-slate-800 p-3">
              <div class="text-xs text-slate-500">分镜</div>
              <div class="mt-1 text-slate-100">{{ result.episode?.storyboard_json?.frame_count || 0 }} 个镜头</div>
              <div class="mt-1 text-xs text-slate-500">{{ result.episode?.storyboard_json?.total_duration || 0 }} 秒</div>
            </div>
            <div class="border border-slate-800 p-3">
              <div class="text-xs text-slate-500">下一步</div>
              <div class="mt-1 text-slate-100">{{ nextGate }}</div>
              <div v-if="isMockResult" class="mt-2 text-xs text-sky-200">
                模拟调度已创建，可进入调度入口查看 worker 队列。
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-if="result.route"
                  class="rounded border border-sky-500/60 px-3 py-1 text-xs text-sky-200"
                  @click="$router.push(result.route)"
                >
                  监控
                </button>
                <button
                  v-if="result.run?.id && !isMockResult"
                  class="rounded border border-amber-500/60 px-3 py-1 text-xs text-amber-200"
                  @click="$router.push(`/ai-video-review?run_id=${result.run.id}`)"
                >
                  审核
                </button>
                <button
                  v-if="isMockResult && result.run?.id"
                  data-test="mock-scheduler-entry"
                  class="rounded border border-sky-500/60 px-3 py-1 text-xs text-sky-200"
                  @click="$router.push(result.route || `/video-production/${result.run.id}`)"
                >
                  调度入口
                </button>
              </div>
            </div>
          </div>

          <div
            v-if="agencyTraceRows.length"
            data-test="agency-trace"
            class="mt-4 border border-slate-800 bg-slate-900/50 p-3 text-sm"
          >
            <div class="mb-2 font-semibold text-slate-200">专家审查轨迹</div>
            <div class="space-y-2">
              <div
                v-for="row in agencyTraceRows"
                :key="row.stage"
                class="border border-slate-800 bg-slate-950/50 p-2"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono text-xs text-sky-200">{{ row.stage }}</span>
                  <span class="text-xs text-slate-300">{{ statusLabel(row.status) }}</span>
                </div>
                <div v-if="row.experts.length" class="mt-1 flex flex-wrap gap-1 text-xs text-slate-300">
                  <span
                    v-for="expert in row.experts"
                    :key="`${row.stage}-${expert}`"
                    class="border border-slate-700 px-2 py-0.5"
                  >
                    {{ expert }}
                  </span>
                </div>
                <div v-if="row.error" class="mt-1 text-xs text-amber-300">{{ row.error }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import AutoRepairPolicyPanel from '../components/agency/AutoRepairPolicyPanel.vue'
import {
  createOneSentenceVideo,
  getVideoProductionRun,
  runRealWorkerStep,
  syncImageStage,
  startVideoStage,
  syncVideoStage,
  startComposeStage,
  syncComposeStage,
} from '../api/videoProduction.js'

const mode = ref('real_short_e2e')
const form = reactive({
  prompt: '',
  title: '',
  target_duration_seconds: 60,
  budget_limit: 1,
  autostart_images: true,
})
const autoRepairPolicy = ref({
  enabled: true,
  allowed_stages: ['style_lock', 'storyboard', 'image_stage', 'video_stage', 'compose'],
  allowed_types: [
    'storyboard_missing_references',
    'image_generation_failed',
    'image_generation_timeout',
    'video_generation_failed',
    'video_generation_timeout',
    'provider_sync_required',
  ],
  max_rounds: 2,
  budget_limit: 0,
  requires_human_gate_after_repair: true,
})
const submitting = ref(false)
const error = ref('')
const repairDetail = ref(null)
const result = ref(null)
const autopilotStatus = ref('')
const autopilotError = ref('')
const autopilotBusy = ref(false)
let autopilotTimer = null

const fallbackSteps = [
  { key: 'prompt', label: '提示词已接收', status: 'waiting' },
  { key: 'series', label: '系列与剧集已创建', status: 'waiting' },
  { key: 'reference_generation', label: '角色与场景参考图', status: 'waiting' },
  { key: 'style_lock', label: '风格已锁定', status: 'waiting' },
  { key: 'storyboard', label: '分镜已生成', status: 'waiting' },
  { key: 'production_plan', label: '生产计划已关联', status: 'waiting' },
  { key: 'image_generation', label: '画面生成', status: 'waiting' },
  { key: 'image_review', label: '画面审核', status: 'waiting' },
  { key: 'video_generation', label: '视频生成', status: 'waiting' },
  { key: 'video_review', label: '视频审核', status: 'waiting' },
  { key: 'compose', label: '最终合成', status: 'waiting' },
  { key: 'final_review', label: '终审', status: 'waiting' },
  { key: 'completed', label: '成片完成', status: 'waiting' },
]

const statusText = {
  waiting: '等待',
  ready: '就绪',
  running: '进行中',
  pending: '待审核',
  done: '完成',
  completed: '完成',
  passed: '通过',
  blocked: '阻断',
  failed: '失败',
  partial: '部分完成',
}
const reviewStatuses = new Set([
  'image_review_pending',
  'image_human_review_required',
  'video_review_pending',
  'video_human_review_required',
  'final_review_pending',
])
const terminalErrorStatuses = new Set(['failed', 'blocked'])
const REAL_SHORT_MAX_SECONDS = 960
const MOCK_SCALE_MAX_SECONDS = 28800

const durationBounds = computed(() => (
  mode.value === 'real_short_e2e'
    ? { min: 60, max: REAL_SHORT_MAX_SECONDS }
    : { min: 60, max: MOCK_SCALE_MAX_SECONDS }
))
const durationHelp = computed(() => (
  mode.value === 'real_short_e2e'
    ? `当前单次真实生产上限 ${REAL_SHORT_MAX_SECONDS} 秒，会拆成多镜头和短片段执行。`
    : '模拟长剧调度允许长时长，可用于 28800 秒等规模测试。'
))
const modeHelp = computed(() => (
  mode.value === 'real_short_e2e'
    ? '真实模式会走端到端生产链路，按镜头分段生成，并受预算和审查闸门控制。'
    : '模拟长剧调度只创建规模化调度入口，用于队列、worker 和长视频编排验证。'
))
const resultRunType = computed(() => result.value?.run?.run_type || mode.value)
const isMockResult = computed(() => resultRunType.value === 'mock_series_scale')
const repairAffectedIds = computed(() => (
  Array.isArray(repairDetail.value?.affected_ids) ? repairDetail.value.affected_ids : []
))
const agencyTraceRows = computed(() => {
  const directTrace = result.value?.agency_trace || {}
  const runTrace = result.value?.run?.model_trace_json?.agency_reviews || {}
  return Object.entries({ ...directTrace, ...runTrace })
    .filter(([, value]) => value && typeof value === 'object')
    .map(([stage, value]) => ({
      stage,
      status: value.stage_status || value.status || '-',
      error: value.error_message || value.error_code || '',
      experts: (value.invocations || [])
        .map(item => item.expert_id || item.role || item.id)
        .filter(Boolean),
    }))
})

const displaySteps = computed(() => {
  const base = result.value?.steps?.length ? result.value.steps : fallbackSteps
  if (!result.value?.run?.status) return base
  return base.map(step => ({
    ...step,
    status: stepStatus(step.key, result.value.run.status),
  }))
})
const nextGate = computed(() => {
  const status = result.value?.run?.status
  if (!status) return '-'
  if (isMockResult.value) return '查看调度入口与 worker 队列'
  if (status === 'reference_generation_running') return '等待后台生成角色与场景参考图'
  if (status === 'reference_generation_blocked') return '参考图生成异常，进入监控页处理'
  if (status.includes('review')) return '等待人工审核'
  if (status.includes('running') || status === 'composing') return '等待供应商结果同步'
  if (status === 'storyboard_ready') return '分镜就绪，可启动画面生成'
  return status
})

function setMode(nextMode) {
  mode.value = nextMode
  if (nextMode === 'real_short_e2e') {
    form.target_duration_seconds = clampRealDuration(form.target_duration_seconds)
  }
}

function clampRealDuration(value) {
  const seconds = Number(value) || 60
  return Math.min(REAL_SHORT_MAX_SECONDS, Math.max(60, seconds))
}

function submitDuration() {
  const seconds = Number(form.target_duration_seconds) || 60
  if (mode.value === 'real_short_e2e') return clampRealDuration(seconds)
  return Math.min(MOCK_SCALE_MAX_SECONDS, Math.max(60, seconds))
}

function isAfterImage(status) {
  return [
    'image_review_pending',
    'image_human_review_required',
    'image_approved',
    'video_batch_running',
    'video_review_pending',
    'video_human_review_required',
    'video_segments_approved',
    'composing',
    'final_review_pending',
    'completed',
  ].includes(status)
}

function isAfterVideo(status) {
  return [
    'video_review_pending',
    'video_human_review_required',
    'video_segments_approved',
    'composing',
    'final_review_pending',
    'completed',
  ].includes(status)
}

function stepStatus(key, runStatus) {
  if (runStatus === 'reference_generation_running') {
    if (['prompt', 'series'].includes(key)) return 'done'
    if (key === 'reference_generation') return 'running'
    return 'waiting'
  }
  if (runStatus === 'reference_generation_blocked') {
    if (['prompt', 'series'].includes(key)) return 'done'
    if (key === 'reference_generation') return 'pending'
    return 'waiting'
  }
  if (['prompt', 'series', 'style_lock', 'storyboard', 'production_plan'].includes(key)) return 'done'
  if (key === 'reference_generation') return 'done'
  if (key === 'image_generation') {
    if (runStatus === 'image_batch_running') return 'running'
    return isAfterImage(runStatus) ? 'done' : 'ready'
  }
  if (key === 'image_review') {
    if (['image_review_pending', 'image_human_review_required'].includes(runStatus)) return 'pending'
    return [
      'image_approved',
      'video_batch_running',
      'video_review_pending',
      'video_human_review_required',
      'video_segments_approved',
      'composing',
      'final_review_pending',
      'completed',
    ].includes(runStatus) ? 'done' : 'waiting'
  }
  if (key === 'video_generation') {
    if (runStatus === 'image_approved') return 'ready'
    if (runStatus === 'video_batch_running') return 'running'
    return isAfterVideo(runStatus) ? 'done' : 'waiting'
  }
  if (key === 'video_review') {
    if (['video_review_pending', 'video_human_review_required'].includes(runStatus)) return 'pending'
    return ['video_segments_approved', 'composing', 'final_review_pending', 'completed'].includes(runStatus) ? 'done' : 'waiting'
  }
  if (key === 'compose') {
    if (runStatus === 'video_segments_approved') return 'ready'
    if (runStatus === 'composing') return 'running'
    return ['final_review_pending', 'completed'].includes(runStatus) ? 'done' : 'waiting'
  }
  if (key === 'final_review') {
    if (runStatus === 'final_review_pending') return 'pending'
    return runStatus === 'completed' ? 'done' : 'waiting'
  }
  if (key === 'completed') return runStatus === 'completed' ? 'done' : 'waiting'
  return 'waiting'
}

function statusLabel(status) {
  return statusText[status] || status || '-'
}

function stepClass(status) {
  if (['done', 'ready'].includes(status)) return 'border-emerald-500/40 bg-emerald-950/30 text-emerald-200'
  if (status === 'running') return 'border-sky-500/40 bg-sky-950/30 text-sky-200'
  if (status === 'pending') return 'border-amber-500/40 bg-amber-950/30 text-amber-200'
  return 'border-slate-800 bg-slate-900/60 text-slate-400'
}

function normalizeError(e) {
  const detail = e.response?.data?.detail
  if (detail && typeof detail === 'object') {
    repairDetail.value = detail
    return detail.message || detail.error_code || JSON.stringify(detail)
  }
  repairDetail.value = null
  return detail || e.message || '操作失败'
}

function isProviderPendingError(message) {
  return String(message || '').toLowerCase().includes('not complete')
}

function isRealProviderRun() {
  return (result.value?.run?.run_type || mode.value) === 'real_short_e2e'
}

function stopAutopilot() {
  if (autopilotTimer) {
    clearInterval(autopilotTimer)
    autopilotTimer = null
  }
}

async function refreshRun() {
  const runId = result.value?.run?.id
  if (!runId) return
  const { data } = await getVideoProductionRun(runId)
  result.value = {
    ...result.value,
    run: data.run,
    assets: result.value.assets || [],
  }
}

async function driveAutopilotOnce() {
  const runId = result.value?.run?.id
  const status = result.value?.run?.status
  if (!runId || autopilotBusy.value) return
  if (status === 'completed') {
    autopilotStatus.value = '生产已完成。'
    stopAutopilot()
    return
  }
  if (reviewStatuses.has(status)) {
    autopilotStatus.value = '已到达审核节点，请打开审核中心继续。'
    stopAutopilot()
    return
  }
  if (terminalErrorStatuses.has(status)) {
    autopilotStatus.value = `生产已进入异常状态：${status || 'unknown'}。请进入监控页查看修复动作。`
    stopAutopilot()
    return
  }
  autopilotBusy.value = true
  autopilotError.value = ''
  try {
    if (status === 'reference_generation_running') {
      autopilotStatus.value = '参考图正在后台生成，页面会继续检查进度...'
      await refreshRun()
    } else if (status === 'image_batch_running') {
      autopilotStatus.value = '正在同步画面生成结果...'
      if (isRealProviderRun()) {
        await runRealWorkerStep(runId)
      } else {
        await syncImageStage(runId)
      }
    } else if (status === 'image_approved') {
      autopilotStatus.value = '正在启动视频片段生成...'
      await startVideoStage(runId)
    } else if (status === 'video_batch_running') {
      autopilotStatus.value = '正在同步视频片段结果...'
      if (isRealProviderRun()) {
        await runRealWorkerStep(runId)
      } else {
        await syncVideoStage(runId)
      }
    } else if (status === 'video_segments_approved') {
      autopilotStatus.value = '正在启动最终合成...'
      await startComposeStage(runId)
    } else if (status === 'composing') {
      autopilotStatus.value = '正在同步最终合成结果...'
      if (isRealProviderRun()) {
        await runRealWorkerStep(runId)
      } else {
        await syncComposeStage(runId)
      }
    } else {
      autopilotStatus.value = status === 'storyboard_ready'
        ? '分镜已就绪，请从监控页启动画面生成。'
        : `等待状态：${status || 'unknown'}。`
    }
    await refreshRun()
  } catch (e) {
    const message = normalizeError(e)
    if (isProviderPendingError(message)) {
      autopilotStatus.value = '供应商任务仍在运行，页面会继续检查。'
      await refreshRun().catch(() => {})
    } else {
      autopilotError.value = message
      stopAutopilot()
    }
  } finally {
    autopilotBusy.value = false
  }
}

function startAutopilot() {
  stopAutopilot()
  driveAutopilotOnce()
  autopilotTimer = setInterval(driveAutopilotOnce, 10000)
}

async function submit() {
  submitting.value = true
  error.value = ''
  repairDetail.value = null
  autopilotError.value = ''
  autopilotStatus.value = ''
  stopAutopilot()
  try {
    const payload = {
      prompt: form.prompt,
      title: form.title || undefined,
      run_type: mode.value,
      target_duration_seconds: submitDuration(),
      autostart_images: form.autostart_images,
      auto_repair_policy: { ...autoRepairPolicy.value },
    }
    if (mode.value === 'real_short_e2e') {
      payload.budget_limit = Number(form.budget_limit || 0)
    }
    const { data } = await createOneSentenceVideo(payload)
    result.value = data
    const submittedRunType = data?.run?.run_type || payload.run_type
    if (submittedRunType === 'mock_series_scale') {
      autopilotStatus.value = '模拟调度已提交，请进入调度入口查看 worker 队列。'
    } else if (submittedRunType === 'real_short_e2e' && payload.autostart_images) {
      startAutopilot()
    }
  } catch (e) {
    error.value = normalizeError(e) || '启动失败'
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(stopAutopilot)
</script>
