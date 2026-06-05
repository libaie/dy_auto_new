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

      <section v-if="activeTab === 'control' && blockingMessage" class="mb-5 rounded-lg border border-rose-500/40 bg-rose-950/40 p-4 text-rose-100">
        <div class="text-sm font-semibold">阻断提示</div>
        <p class="mt-1 text-sm leading-6">{{ blockingMessage }}</p>
      </section>

      <AutoRepairSummaryStrip
        v-if="activeTab === 'control' && repairSummary.total"
        class="mb-5"
        :summary="repairSummary"
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
import { getAgencyConsole } from '../api/series.js'
import AgencyDecisionLog from '../components/agency/AgencyDecisionLog.vue'
import AgencyExpertDrawer from '../components/agency/AgencyExpertDrawer.vue'
import AgencyInvocationGraph from '../components/agency/AgencyInvocationGraph.vue'
import AgencyStageRail from '../components/agency/AgencyStageRail.vue'
import AgencyStatusBadge from '../components/agency/AgencyStatusBadge.vue'
import AgencyTeamMap2D from '../components/agency/AgencyTeamMap2D.vue'
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'
import { expertRoleGroup, phaseLabel, safeDisplayText, stepName } from '../components/agency/agencyExpertLabels.js'

const route = useRoute()
const router = useRouter()
const AgencyTeamMap3D = defineAsyncComponent(() => import('../components/agency/AgencyTeamMap3D.vue'))
const consoleData = ref(null)
const selectedExpertId = ref('')
const loading = ref(true)
const error = ref('')
const activeTab = ref(route.query?.tab === 'experts' ? 'experts' : 'control')
let disposed = false

const stageGraph = computed(() => consoleData.value?.stage_graph || [])
const expertTeam = computed(() => consoleData.value?.expert_team || [])
const expertInvocations = computed(() => consoleData.value?.expert_invocations || [])
const decisionLog = computed(() => consoleData.value?.decision_log || [])
const productionSteps = computed(() => consoleData.value?.production_steps || [])
const repairSummary = computed(() => consoleData.value?.repair_summary || {})
const qualityExpertCount = computed(() => expertTeam.value.filter(expert => expertRoleGroup(expert) === 'quality').length)

const isEmpty = computed(() => {
  if (!consoleData.value) return true
  return !stageGraph.value.length && !expertInvocations.value.length && !productionSteps.value.length
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

async function load() {
  if (disposed) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await getAgencyConsole(route.params.seriesId)
    if (disposed) return
    if (!data?.ok) throw new Error('加载失败')
    consoleData.value = data
  } catch (err) {
    if (disposed) return
    console.error('Agency console load failed', err)
    error.value = '专家控制台加载失败，请稍后重试。'
  } finally {
    if (!disposed) loading.value = false
  }
}

onMounted(load)

onBeforeUnmount(() => {
  disposed = true
})
</script>
