<!-- 管理端业务页面：承载 AgencyConsolePage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <main class="min-h-screen bg-zinc-950 px-4 py-5 text-zinc-100 md:px-6">
    <button class="mb-4 rounded border border-white/10 px-3 py-2 text-sm text-cyan-200 hover:border-cyan-400/60 hover:text-cyan-100" @click="router.back()">返回</button>

    <section v-if="loading" class="rounded-lg border border-white/10 bg-zinc-900/80 p-6 text-zinc-300">
      正在加载专家控制台...
    </section>
    <section v-else-if="error" class="rounded-lg border border-rose-500/40 bg-rose-950/40 p-6 text-rose-100">
      {{ error }}
    </section>
    <section v-else-if="isEmpty" class="rounded-lg border border-white/10 bg-zinc-900/80 p-8">
      <h1 class="text-xl font-semibold">暂无可回放的专家生产过程</h1>
      <p class="mt-2 text-sm text-zinc-400">生成流程启动后，这里会展示专家参与过程。</p>
    </section>

    <template v-else>
      <header v-if="activeTab === 'control'" class="mb-5 overflow-hidden rounded-lg border border-white/10 bg-zinc-900/90 shadow-2xl shadow-black/30">
        <div class="grid gap-4 border-b border-white/10 p-5 xl:grid-cols-[minmax(0,1fr)_auto]">
          <div>
            <div class="inline-flex rounded border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-medium text-cyan-100">
              专家团队透明控制台
            </div>
            <h1 class="mt-3 text-2xl font-semibold tracking-normal text-white md:text-3xl">AI 视频生产指挥台</h1>
            <p class="mt-2 text-sm leading-6 text-zinc-300">
              {{ consoleData.series?.title || '未命名系列' }} · 展示专家团队如何编排、审查和推进每个生产阶段。
            </p>
          </div>
          <div class="flex items-start justify-start xl:justify-end">
            <AgencyStatusBadge :status="consoleData.agency_trace_status" />
          </div>
        </div>

        <section class="grid gap-px bg-white/10 md:grid-cols-4" aria-label="生产总览">
          <article
            v-for="metric in commandMetrics"
            :key="metric.label"
            class="bg-zinc-900 px-4 py-4"
          >
            <div class="text-xs font-medium text-zinc-500">{{ metric.label }}</div>
            <div class="mt-1 text-2xl font-semibold text-white">{{ metric.value }}</div>
            <p class="mt-1 min-h-5 text-xs leading-5 text-zinc-400">{{ metric.hint }}</p>
          </article>
        </section>
      </header>

      <section
        v-if="activeTab === 'control' && blockingMessage"
        data-test="agency-blocking-message"
        class="mb-5 rounded-lg border border-rose-500/40 bg-rose-950/40 p-4 text-rose-100"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="text-sm font-semibold">阻断提示</div>
            <p class="mt-1 text-sm leading-6">{{ blockingMessage }}</p>
            <p class="mt-1 text-xs leading-5 text-rose-100/75">修复线索在下方「决策日志」卡片的「必须修改 / 下一步 / 返修动作」字段。</p>
          </div>
          <button
            type="button"
            data-test="jump-to-decision-log"
            class="rounded-md border border-rose-200/50 px-3 py-2 text-xs font-medium text-rose-50 hover:bg-rose-200/10"
            @click="scrollToDecisionLog"
          >
            跳到决策日志
          </button>
        </div>
      </section>

      <AutoRepairSummaryStrip
        v-if="activeTab === 'control' && repairSummary.total"
        class="mb-5"
        :summary="repairSummary"
      />
      <AutoRepairTaskList
        v-if="activeTab === 'control' && (repairTasks.length || repairLoading || repairError)"
        class="mb-5"
        :tasks="repairTasks"
        :loading="repairLoading"
        :error="repairError"
        :busy-id="repairBusyId"
        @manual-action="handleRepairManualAction"
        @retry="retryRepairTask"
      />

      <CreativePatchSummaryStrip
        v-if="activeTab === 'control' && creativePatchSummary.total"
        class="mb-5"
        :summary="creativePatchSummary"
      />

      <nav class="mb-5 inline-flex rounded-lg border border-white/10 bg-zinc-900/80 p-1" aria-label="专家控制台视图">
        <button
          type="button"
          data-tab="control"
          class="rounded-md px-4 py-2 text-sm font-medium transition"
          :class="activeTab === 'control' ? 'bg-cyan-400 text-zinc-950 shadow shadow-cyan-950/40' : 'text-zinc-300 hover:bg-white/5 hover:text-white'"
          @click="activeTab = 'control'"
        >
          生产指挥台
        </button>
        <button
          type="button"
          data-tab="workbench"
          class="rounded-md px-4 py-2 text-sm font-medium transition"
          :class="activeTab === 'workbench' ? 'bg-cyan-400 text-zinc-950 shadow shadow-cyan-950/40' : 'text-zinc-300 hover:bg-white/5 hover:text-white'"
          @click="activeTab = 'workbench'"
        >
          短视频导演台
        </button>
        <button
          type="button"
          data-tab="experts"
          class="rounded-md px-4 py-2 text-sm font-medium transition"
          :class="activeTab === 'experts' ? 'bg-cyan-400 text-zinc-950 shadow shadow-cyan-950/40' : 'text-zinc-300 hover:bg-white/5 hover:text-white'"
          @click="activeTab = 'experts'"
        >
          3D 专家人物化
        </button>
      </nav>

      <section v-if="activeTab === 'control'" class="grid gap-4 2xl:grid-cols-[260px_minmax(0,1fr)_340px]">
        <AgencyStageRail :stages="stageGraph" />

        <div class="min-w-0 space-y-4">
          <AgencyInvocationGraph
            :stages="stageGraph"
            :expert-team="expertTeam"
            :invocations="expertInvocations"
            @select-expert="openExpert"
          />

          <section v-if="productionSteps.length" class="rounded-lg border border-white/10 bg-zinc-900/80 p-4">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="text-lg font-semibold text-white">生产步骤</h2>
                <p class="mt-1 text-xs text-zinc-500">按流水线顺序展示，不影响后台生成进度。</p>
              </div>
              <span class="rounded border border-amber-300/30 bg-amber-300/10 px-2 py-1 text-xs text-amber-100">透明记录</span>
            </div>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <article
                v-for="step in productionSteps"
                :key="step.id"
                class="rounded-md border border-white/10 bg-zinc-950/70 p-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <h3 class="text-sm font-medium text-zinc-100">{{ stepLabel(step) }}</h3>
                  <AgencyStatusBadge :status="step.status" />
                </div>
                <p class="mt-2 text-xs leading-5 text-zinc-400">{{ stepSummary(step) }}</p>
              </article>
            </div>
          </section>

          <AgencyDecisionLog
            :items="decisionLog"
            :expert-team="expertTeam"
            :stages="stageGraph"
            @manual-action="handleRepairManualAction"
            @retry="retryRepairTask"
          />
        </div>

        <aside class="space-y-4">
          <section class="rounded-lg border border-cyan-400/20 bg-cyan-950/20 p-4">
            <h2 class="text-base font-semibold text-cyan-50">专家席位</h2>
            <p class="mt-2 text-sm leading-6 text-cyan-100/80">核心专家与支援专家按阶段接力；需要看人物化空间关系时进入 3D 视图。</p>
            <button
              type="button"
              class="mt-3 w-full rounded-md border border-cyan-300/40 bg-cyan-300/10 px-3 py-2 text-sm font-medium text-cyan-50 hover:border-cyan-200"
              @click="activeTab = 'experts'"
            >
              进入 3D 专家人物化
            </button>
          </section>
          <AgencyTeamMap2D :experts="expertTeam" @select="openExpert" />
        </aside>
      </section>

      <CreativePatchWorkbench
        v-else-if="activeTab === 'workbench'"
        :summary="creativePatchSummary"
        :patches="creativePatches"
        :loading="patchLoading"
        :error="patchError"
        :busy-id="patchBusyId"
        @save="saveCreativePatch"
        @approve="approveCreativePatch"
        @reject="rejectCreativePatch"
        @apply="applyCreativePatch"
        @open-invocation="openPatchInvocation"
      />

      <AgencyTeamMap3D
        v-else
        :experts="expertTeam"
        :stage-graph="stageGraph"
        :invocations="expertInvocations"
        @select="openExpert"
      />
      <AgencyExpertDrawer :expert-id="selectedExpertId" @close="selectedExpertId = ''" />
    </template>
  </main>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  applyAgencyCreativePatch,
  authorizeAgencyRepairRetry,
  approveAgencyCreativePatch,
  listAgencyCreativePatches,
  listAgencyRepairTasks,
  rejectAgencyCreativePatch,
  retryAgencyRepairTask,
  updateAgencyCreativePatch,
} from '../api/agency.js'
import { getAgencyConsole } from '../api/series.js'
import AgencyDecisionLog from '../components/agency/AgencyDecisionLog.vue'
import AgencyExpertDrawer from '../components/agency/AgencyExpertDrawer.vue'
import AgencyInvocationGraph from '../components/agency/AgencyInvocationGraph.vue'
import AgencyStageRail from '../components/agency/AgencyStageRail.vue'
import AgencyStatusBadge from '../components/agency/AgencyStatusBadge.vue'
import AgencyTeamMap2D from '../components/agency/AgencyTeamMap2D.vue'
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'
import AutoRepairTaskList from '../components/agency/AutoRepairTaskList.vue'
import CreativePatchSummaryStrip from '../components/agency/CreativePatchSummaryStrip.vue'
import CreativePatchWorkbench from '../components/agency/CreativePatchWorkbench.vue'
import { expertRoleGroup, phaseLabel, safeDisplayText, stepName } from '../components/agency/agencyExpertLabels.js'

const route = useRoute()
const router = useRouter()
const AgencyTeamMap3D = defineAsyncComponent(() => import('../components/agency/AgencyTeamMap3D.vue'))
const consoleData = ref(null)
const selectedExpertId = ref('')
const loading = ref(true)
const error = ref('')
const activeTab = ref(route.query?.tab === 'experts' ? 'experts' : route.query?.tab === 'workbench' ? 'workbench' : 'control')
const creativePatches = ref([])
const patchLoading = ref(false)
const patchError = ref('')
const patchBusyId = ref('')
const repairTasks = ref([])
const repairTaskSummary = ref({})
const repairLoading = ref(false)
const repairError = ref('')
const repairBusyId = ref('')
let disposed = false
let consolePollTimer = null

const CONSOLE_POLL_INTERVAL_MS = 5000
const TERMINAL_RUN_STATUSES = new Set(['completed', 'cancelled', 'failed_terminal'])

const stageGraph = computed(() => consoleData.value?.stage_graph || [])
const expertTeam = computed(() => consoleData.value?.expert_team || [])
const expertInvocations = computed(() => consoleData.value?.expert_invocations || [])
const decisionLog = computed(() => consoleData.value?.decision_log || [])
const productionSteps = computed(() => consoleData.value?.production_steps || [])
const repairSummary = computed(() => (
  Object.keys(repairTaskSummary.value || {}).length ? repairTaskSummary.value : consoleData.value?.repair_summary || {}
))
const creativePatchSummary = computed(() => consoleData.value?.creative_patch_summary || {})
const qualityExpertCount = computed(() => expertTeam.value.filter(expert => expertRoleGroup(expert) === 'quality').length)

const isEmpty = computed(() => {
  if (!consoleData.value) return true
  return !stageGraph.value.length && !expertInvocations.value.length && !productionSteps.value.length && !creativePatches.value.length
})

const blockingMessage = computed(() => {
  if (!consoleData.value) return ''
  const failedStage = stageGraph.value.find(stage => ['failed', 'blocked'].includes(stage.status))
  if (['failed', 'blocked'].includes(consoleData.value.agency_trace_status) || failedStage) {
    return '专家轨迹存在阻断，请查看决策日志中的修复线索。'
  }
  return ''
})

const activeStage = computed(() => (
  stageGraph.value.find(stage => ['running', 'pending', 'queued', 'blocked', 'failed'].includes(stage.status)) ||
  stageGraph.value[stageGraph.value.length - 1]
))

const commandMetrics = computed(() => [
  {
    label: '生产总览',
    value: `${stageGraph.value.length} 个阶段`,
    hint: activeStage.value ? `当前：${stageLabel(activeStage.value)}` : '等待生产轨迹',
  },
  {
    label: '专家席位',
    value: `${expertTeam.value.length} 位`,
    hint: `${expertTeam.value.length} 位当前专家，${qualityExpertCount.value} 个阶段质量门`,
  },
  {
    label: '调用记录',
    value: `${expertInvocations.value.length} 次`,
    hint: expertInvocations.value.length ? '可追溯每次专家输出' : '等待专家调用',
  },
  {
    label: '生产步骤',
    value: `${productionSteps.value.length} 步`,
    hint: '不打断后台生成流程',
  },
])

function openExpert(expertId) {
  selectedExpertId.value = expertId
}

function scrollToDecisionLog() {
  document.getElementById('agency-decision-log')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function stageLabel(stage) {
  return phaseLabel(stage?.stage, stage?.label)
}

function stepLabel(step) {
  return stepName(step)
}

function stepSummary(step) {
  const text = step.summary || step.next_action || ''
  if (!text) return '等待该步骤产生记录。'
  return safeDisplayText(text, '该步骤已记录运行摘要。')
}

async function load(options = {}) {
  if (disposed) return
  const silent = options?.silent === true
  if (!silent) loading.value = true
  error.value = ''
  try {
    const { data } = await getAgencyConsole(route.params.seriesId)
    if (disposed) return
    if (!data?.ok) throw new Error('加载失败')
    consoleData.value = data
    creativePatches.value = data.creative_patches || []
    await Promise.all([
      ((data.creative_patch_summary?.total || 0) > 0 || creativePatches.value.length)
        ? refreshCreativePatches()
        : Promise.resolve(),
      refreshRepairTasks(),
    ])
  } catch (err) {
    if (disposed) return
    console.error('Agency console load failed', err)
    error.value = '专家控制台加载失败，请稍后重试。'
  } finally {
    if (!disposed && !silent) loading.value = false
    scheduleConsolePoll()
  }
}

async function refreshCreativePatches() {
  if (disposed) return
  patchLoading.value = true
  patchError.value = ''
  try {
    const params = { series_id: route.params.seriesId }
    const runId = consoleData.value?.latest_run?.id
    if (runId) params.run_id = runId
    const { data } = await listAgencyCreativePatches(params)
    if (disposed) return
    creativePatches.value = data?.items || []
    if (consoleData.value) {
      consoleData.value = {
        ...consoleData.value,
        creative_patch_summary: data?.summary || {},
      }
    }
  } catch (err) {
    if (disposed) return
    console.error('Creative patch load failed', err)
    patchError.value = '创作补丁加载失败，请稍后重试。'
  } finally {
    if (!disposed) patchLoading.value = false
  }
}

function normalizeRepairTask(task) {
  const retryActions = { ...(task?.retry_actions || {}) }
  if (retryActions.paid_authorization_required === undefined && retryActions.paid_authorize_required !== undefined) {
    retryActions.paid_authorization_required = retryActions.paid_authorize_required
  }
  return { ...(task || {}), retry_actions: retryActions }
}

function repairTaskParams() {
  const params = { series_id: route.params.seriesId, page: 1, page_size: 20 }
  const runId = consoleData.value?.latest_run?.id
  if (runId) params.run_id = runId
  return params
}

async function refreshRepairTasks() {
  if (disposed || !consoleData.value) return
  repairLoading.value = true
  repairError.value = ''
  try {
    const { data } = await listAgencyRepairTasks(repairTaskParams())
    if (disposed) return
    repairTasks.value = (data?.items || []).map(normalizeRepairTask)
    repairTaskSummary.value = data?.summary || {}
  } catch (err) {
    if (disposed) return
    console.error('Repair task load failed', err)
    repairTasks.value = []
    repairTaskSummary.value = {}
    repairError.value = '返修任务加载失败，请稍后重试。'
  } finally {
    if (!disposed) repairLoading.value = false
  }
}

async function handleCreativePatchAction(patch, action) {
  if (!patch?.id) return
  patchBusyId.value = patch.id
  patchError.value = ''
  try {
    await action()
    await refreshCreativePatches()
  } catch (err) {
    console.error('Creative patch action failed', err)
    patchError.value = '创作补丁处理失败，请稍后重试。'
  } finally {
    patchBusyId.value = ''
  }
}

function saveCreativePatch(patch) {
  return handleCreativePatchAction(patch, () => updateAgencyCreativePatch(patch.id, { after: patch.after || {} }))
}

function approveCreativePatch(patch) {
  return handleCreativePatchAction(patch, () => approveAgencyCreativePatch(patch.id))
}

function rejectCreativePatch(patch) {
  return handleCreativePatchAction(patch, () => rejectAgencyCreativePatch(patch.id, { reason: '人工拒绝该补丁' }))
}

function applyCreativePatch(patch) {
  return handleCreativePatchAction(patch, () => applyAgencyCreativePatch(patch.id))
}

function openPatchInvocation() {
  activeTab.value = 'control'
}

function handleRepairManualAction(task) {
  if (!task?.repair_route) return
  if (String(task.repair_route).startsWith('/')) {
    router.push(task.repair_route)
    return
  }
  window.location.href = task.repair_route
}

async function retryRepairTask(task, authorizationPayload = null) {
  if (!task?.id || repairBusyId.value) return
  repairBusyId.value = task.id
  repairError.value = ''
  try {
    if (authorizationPayload) {
      await authorizeAgencyRepairRetry(task.id, authorizationPayload)
    } else {
      await retryAgencyRepairTask(task.id)
    }
    await load({ silent: true })
  } catch (err) {
    console.error('Repair retry failed', err)
    repairError.value = '返修重试失败，请稍后重试。'
  } finally {
    repairBusyId.value = ''
  }
}

function shouldPollConsole() {
  const status = consoleData.value?.latest_run?.status
  return Boolean(status && !TERMINAL_RUN_STATUSES.has(status))
}

function scheduleConsolePoll() {
  if (consolePollTimer) {
    clearTimeout(consolePollTimer)
    consolePollTimer = null
  }
  if (!disposed && shouldPollConsole()) {
    consolePollTimer = setTimeout(() => load({ silent: true }), CONSOLE_POLL_INTERVAL_MS)
  }
}

onMounted(load)

onBeforeUnmount(() => {
  disposed = true
  if (consolePollTimer) clearTimeout(consolePollTimer)
})
</script>
