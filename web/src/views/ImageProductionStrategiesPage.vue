<!-- 管理端业务页面：承载 ImageProductionStrategiesPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="min-h-full bg-slate-950 px-4 py-6 text-slate-100 sm:px-6">
    <div class="mx-auto max-w-7xl">
      <header class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl font-bold">图像策略中心</h1>
          <p class="mt-1 text-sm text-slate-400">管理图像生产策略、版本和审查入口。</p>
        </div>
        <button
          type="button"
          data-testid="refresh-image-metrics"
          class="min-h-11 border border-emerald-500/40 px-4 py-2 text-sm font-medium text-emerald-100 hover:bg-emerald-950/40"
          @click="refreshMetrics"
        >
          刷新质量指标
        </button>
        <button
          type="button"
          class="min-h-11 border border-sky-500/40 px-4 py-2 text-sm font-medium text-sky-100 hover:bg-sky-950/50"
          @click="loadStrategies"
        >
          刷新策略
        </button>
      </header>

      <p v-if="error" role="alert" class="mb-4 border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
        {{ error }}
      </p>
      <p
        v-if="metricsMessage"
        data-testid="image-metrics-message"
        role="status"
        aria-live="polite"
        class="mb-4 border border-emerald-500/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100"
      >
        {{ metricsMessage }}
      </p>

      <section class="overflow-hidden border border-slate-800 bg-slate-950/70">
        <div class="hidden grid-cols-[minmax(220px,1fr)_150px_180px_140px_90px_150px_180px] border-b border-slate-800 px-4 py-3 text-xs font-semibold text-slate-400 md:grid">
          <span>策略</span>
          <span>用途</span>
          <span>默认模型</span>
          <span>Fallback</span>
          <span>版本</span>
          <span>指标</span>
          <span>操作</span>
        </div>
        <div v-if="loading" class="px-4 py-8 text-sm text-slate-400">加载中...</div>
        <div v-else-if="strategies.length === 0" class="px-4 py-8 text-sm text-slate-400">暂无策略。</div>
        <div
          v-for="strategy in strategies"
          v-else
          :key="strategy.id"
          class="grid gap-3 border-b border-slate-900 px-4 py-4 text-sm last:border-b-0 md:grid-cols-[minmax(220px,1fr)_150px_180px_140px_90px_150px_180px] md:items-center md:gap-0 md:py-3"
        >
          <div>
            <p class="font-medium text-slate-100">{{ strategy.name }}</p>
            <p class="mt-1 break-all font-mono text-xs text-slate-500">{{ strategy.id }}</p>
            <span class="mt-2 inline-block w-fit border px-2 py-1 text-xs md:hidden" :class="statusClass(strategy.status)">
              {{ statusLabel(strategy.status) }}
            </span>
          </div>
          <div>
            <span class="mb-1 block text-xs font-semibold text-slate-500 md:hidden">用途</span>
            <span class="text-slate-300">{{ roleLabel(strategy.destination_role) }}</span>
          </div>
          <div>
            <span class="mb-1 block text-xs font-semibold text-slate-500 md:hidden">默认模型</span>
            <span class="text-slate-300">{{ modelName(strategy.default_model_id) }}</span>
          </div>
          <div>
            <span class="mb-1 block text-xs font-semibold text-slate-500 md:hidden">Fallback</span>
            <span class="text-slate-300">{{ (strategy.fallback_model_ids || []).length }} 个</span>
          </div>
          <div>
            <span class="mb-1 block text-xs font-semibold text-slate-500 md:hidden">版本</span>
            <span>v{{ strategy.version }}</span>
          </div>
          <div>
            <span class="mb-1 block text-xs font-semibold text-slate-500 md:hidden">指标</span>
            <div class="space-y-1 text-xs text-slate-300">
              <p>{{ successRateLabel(strategy.metrics) }}</p>
              <p>{{ costLabel(strategy.metrics) }}</p>
              <p>{{ latencyLabel(strategy.metrics) }}</p>
              <p v-if="strategy.metrics?.low_sample" class="text-amber-300">样本不足</p>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              :data-testid="`edit-strategy-${strategy.id}`"
              class="min-h-11 border border-sky-500/40 px-3 py-2 text-xs text-sky-100 hover:bg-sky-950/50"
              @click="openEditor(strategy)"
            >
              编辑
            </button>
            <button
              type="button"
              :data-testid="`archive-strategy-${strategy.id}`"
              class="min-h-11 border border-amber-500/40 px-3 py-2 text-xs text-amber-200 hover:bg-amber-950/40 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="strategy.status === 'archived'"
              @click="archive(strategy.id)"
            >
              归档
            </button>
            <button
              type="button"
              :data-testid="`show-strategy-recommendation-${strategy.id}`"
              class="min-h-11 border border-cyan-500/40 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-950/40 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="recommendationLoadingId === strategy.id"
              @click="showRecommendation(strategy.id)"
            >
              质量建议
            </button>
          </div>
        </div>
      </section>

      <section
        v-if="activeRecommendation || recommendationError"
        data-testid="strategy-recommendation-panel"
        class="mt-4 border border-slate-800 bg-slate-950/70 p-4"
      >
        <p v-if="recommendationError" role="alert" class="text-sm text-rose-300">{{ recommendationError }}</p>
        <div v-else-if="activeRecommendation" role="status" aria-live="polite">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold">策略质量建议</h2>
              <p class="mt-1 text-sm text-slate-400">
                {{ activeRecommendation.strategy_name || activeRecommendation.strategy_id }} 路 v{{ activeRecommendation.strategy_version }}
              </p>
            </div>
            <div class="text-right">
              <p class="text-sm text-slate-400">{{ recommendationStatusLabel(activeRecommendation.status) }}</p>
              <p class="text-xl font-semibold text-slate-100">质量评分 {{ activeRecommendation.quality_score }}</p>
            </div>
          </div>
          <div class="mt-4 grid gap-3 md:grid-cols-2">
            <article
              v-for="item in activeRecommendation.recommendations || []"
              :key="item.code"
              class="border border-slate-800 bg-slate-900/60 p-3 text-sm"
            >
              <p class="font-medium text-slate-100">{{ item.title || item.message || item.code }}</p>
              <p v-if="item.description" class="mt-1 text-slate-400">{{ item.description }}</p>
            </article>
          </div>
          <p class="mt-4 text-xs text-amber-200">策略变更仍需人工确认</p>
        </div>
      </section>

      <section v-if="editing" class="mt-4 border border-slate-800 bg-slate-950/70 p-4">
        <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="text-lg font-semibold">编辑模型配置</h2>
            <p class="mt-1 text-sm text-slate-400">{{ editing.name }} · v{{ editing.version }}</p>
          </div>
          <button
            type="button"
            class="min-h-11 border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:bg-slate-900"
            @click="closeEditor"
          >
            关闭
          </button>
        </div>

        <p
          v-if="editorError"
          data-testid="strategy-editor-error"
          role="alert"
          class="mb-4 border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200"
        >
          {{ editorError }}
        </p>

        <div class="grid gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-300">默认模型</span>
            <select
              v-model="editor.default_model_id"
              data-testid="strategy-default-model"
              class="min-h-11 w-full border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="">自动</option>
              <option v-for="model in imageModels" :key="model.id" :value="model.id">
                {{ modelOptionLabel(model) }}
              </option>
            </select>
          </label>

          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-300">Fallback 模型</span>
            <select
              v-model="editor.fallback_model_ids"
              data-testid="strategy-fallback-models"
              multiple
              class="min-h-32 w-full border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option v-for="model in imageModels" :key="model.id" :value="model.id">
                {{ modelOptionLabel(model) }}
              </option>
            </select>
          </label>
        </div>

        <div class="mt-4 flex justify-end">
          <button
            type="button"
            data-testid="save-strategy-editor"
            class="min-h-11 border border-emerald-500/40 px-4 py-2 text-sm font-medium text-emerald-100 hover:bg-emerald-950/40"
            @click="saveEditor"
          >
            保存配置
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { listModels } from '../api/aiConfig.js'
import {
  archiveImageProductionStrategy,
  getImageProductionStrategyRecommendations,
  listImageProductionStrategies,
  refreshImageProductionMetrics,
  updateImageProductionStrategy,
} from '../api/imageProduction.js'

const strategies = ref([])
const imageModels = ref([])
const editing = ref(null)
const loading = ref(false)
const error = ref('')
const editorError = ref('')
const metricsMessage = ref('')
const recommendationLoadingId = ref('')
const recommendationError = ref('')
const activeRecommendation = ref(null)
const latestRecommendationRequestId = ref(0)
const editor = reactive({
  default_model_id: '',
  fallback_model_ids: [],
})

const roleLabels = {
  character_anchor_image: '角色锚定图',
  scene_reference_image: '场景参考图',
  style_reference_image: '风格参考图',
  storyboard_first_frame: '分镜首帧',
  image_to_video_input: '图生视频输入图',
  repaint_image: '重绘图',
  fusion_image: '融合图',
  batch_story_images: '批量故事图',
}

const statusLabels = {
  active: '启用',
  archived: '已归档',
  disabled: '停用',
}

function normalizeError(e) {
  return errorText(
    e.response?.data?.detail?.user_message
      || e.response?.data?.detail
      || e.response?.data?.message
      || e.message
      || '操作失败，请稍后重试',
  )
}

function errorText(value) {
  if (typeof value === 'string') return value
  if (!value) return '操作失败，请稍后重试'
  if (typeof value === 'object') {
    return value.user_message || value.message || value.detail || JSON.stringify(value)
  }
  return String(value)
}

function roleLabel(role) {
  return roleLabels[role] || role || '未指定'
}

function statusLabel(status) {
  return statusLabels[status] || status || '未知'
}

function statusClass(status) {
  if (status === 'active') return 'border-emerald-500/40 text-emerald-300'
  if (status === 'archived') return 'border-slate-700 text-slate-400'
  return 'border-amber-500/40 text-amber-300'
}

function recommendationStatusLabel(status) {
  if (status === 'recommended') return '推荐使用'
  if (status === 'cautious') return '谨慎观察'
  if (status === 'disabled') return '建议停用'
  if (status === 'monitor') return '继续观察'
  return '待评估'
}

function modelName(modelId) {
  if (!modelId) return '自动'
  const model = imageModels.value.find((item) => item.id === modelId)
  return model?.name || modelId
}

function modelOptionLabel(model) {
  return `${model.name || model.id} · ${model.provider || model.model_name || model.id}`
}

function successRateLabel(metrics) {
  return `${Math.round(((metrics?.success_rate ?? 0) * 100))}%`
}

function costLabel(metrics) {
  return `${metrics?.average_cost_amount ?? 0} ${metrics?.currency || 'CNY'}`
}

function latencyLabel(metrics) {
  return `${metrics?.average_latency_seconds ?? 0}s`
}

function normalizeModels(response) {
  const data = response?.data?.data || response?.data || response || {}
  if (Array.isArray(data.models)) return data.models
  if (Array.isArray(data.items)) return data.items
  return Array.isArray(data) ? data : []
}

async function loadStrategies() {
  loading.value = true
  error.value = ''
  try {
    const response = await listImageProductionStrategies({ include_metrics: true })
    const data = response?.data?.data || response?.data || response || {}
    strategies.value = Array.isArray(data.strategies) ? data.strategies : []
  } catch (e) {
    error.value = normalizeError(e)
  } finally {
    loading.value = false
  }
}

async function loadImageModels() {
  try {
    const response = await listModels({ model_type: 'image', enabled: true })
    imageModels.value = normalizeModels(response)
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function refreshMetrics() {
  metricsMessage.value = ''
  error.value = ''
  try {
    const response = await refreshImageProductionMetrics({})
    const refreshed = response?.data?.refreshed || response?.data?.data?.refreshed || {}
    metricsMessage.value = `已刷新 ${refreshed.refreshed_count || 0} 组指标`
    await loadStrategies()
  } catch (e) {
    error.value = normalizeError(e)
  }
}

async function showRecommendation(strategyId) {
  const requestId = latestRecommendationRequestId.value + 1
  latestRecommendationRequestId.value = requestId
  recommendationLoadingId.value = strategyId
  recommendationError.value = ''
  activeRecommendation.value = null
  try {
    const response = await getImageProductionStrategyRecommendations(strategyId)
    if (requestId !== latestRecommendationRequestId.value) return
    activeRecommendation.value = response?.data?.recommendation || response?.data?.data?.recommendation || null
  } catch (e) {
    if (requestId !== latestRecommendationRequestId.value) return
    recommendationError.value = normalizeError(e)
  } finally {
    if (requestId === latestRecommendationRequestId.value) {
      recommendationLoadingId.value = ''
    }
  }
}

function openEditor(strategy) {
  editorError.value = ''
  editing.value = strategy
  editor.default_model_id = strategy.default_model_id || ''
  editor.fallback_model_ids = [...(strategy.fallback_model_ids || [])]
}

function closeEditor() {
  editorError.value = ''
  editing.value = null
  editor.default_model_id = ''
  editor.fallback_model_ids = []
}

async function saveEditor() {
  if (!editing.value) return
  error.value = ''
  editorError.value = ''
  const strategy = editing.value
  const payload = {
    slug: strategy.slug,
    name: strategy.name,
    description: strategy.description,
    destination_role: strategy.destination_role,
    supported_modes: strategy.supported_modes || [],
    default_model_id: editor.default_model_id || null,
    fallback_model_ids: [...editor.fallback_model_ids],
    common_parameters: strategy.common_parameters || {},
    provider_options: strategy.provider_options || {},
    review_policy_version_id: strategy.review_policy_version_id || null,
    cost_policy_version_id: strategy.cost_policy_version_id || null,
    capacity_policy_version_id: strategy.capacity_policy_version_id || null,
    ab_test_policy_version_id: strategy.ab_test_policy_version_id || null,
    version: strategy.version,
  }

  try {
    await updateImageProductionStrategy(strategy.id, payload)
    closeEditor()
    await loadStrategies()
  } catch (e) {
    editorError.value = normalizeError(e)
  }
}

async function archive(id) {
  error.value = ''
  try {
    await archiveImageProductionStrategy(id)
    await loadStrategies()
  } catch (e) {
    error.value = normalizeError(e)
  }
}

onMounted(() => {
  loadStrategies()
  loadImageModels()
})
</script>
