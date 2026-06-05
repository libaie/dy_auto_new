<template>
  <div class="p-6">
    <div class="mb-6 flex items-start justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">AI 视频审查中心</h1>
        <p class="mt-1 text-sm text-slate-500">人工确认分阶段视频生产素材。</p>
      </div>
      <div class="flex gap-2">
        <button
          v-if="runId && runStatus && (runStatus === 'image_batch_running' || runStatus === 'image_generation')"
          @click="doSync"
          :disabled="syncing"
          class="cursor-pointer rounded-lg bg-amber-600 px-4 py-2 text-sm text-white transition hover:bg-amber-500 disabled:opacity-50"
        >
          {{ syncButtonText }}
        </button>
        <button @click="load" class="cursor-pointer rounded-lg bg-sky-500 px-4 py-2 text-sm text-white transition hover:bg-sky-400">
          刷新
        </button>
      </div>
    </div>

    <div
      v-if="runId && runStatus"
      class="mb-4 rounded-lg px-4 py-2 text-sm"
      :class="runStatus === 'image_review_pending' ? 'bg-amber-900/30 text-amber-300' : 'bg-slate-800/40 text-slate-400'"
    >
      运行状态：{{ runStatus }}
    </div>

    <div v-if="notice" class="mb-4 rounded-lg border border-sky-500/40 bg-sky-950/30 p-3 text-sm text-sky-100">
      {{ notice }}
    </div>

    <div v-if="runId && (repairSummary.total || repairTasks.length || repairLoading || repairError)" class="mb-4 space-y-3">
      <AutoRepairSummaryStrip :summary="repairSummary" />
      <AutoRepairTaskList
        :tasks="repairTasks"
        :loading="repairLoading"
        :error="repairError"
        :busy-id="repairBusyId"
        @retry="retryRepairTask"
        @manual-action="openRepairAction"
      />
    </div>

    <div v-if="loading" class="py-12 text-center text-slate-400">正在加载审查队列...</div>
    <div v-else-if="error" class="py-12 text-center text-red-400">{{ error }}</div>
    <div v-else class="grid grid-cols-[320px_1fr] gap-4">
      <aside class="overflow-hidden rounded-xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.55);">
        <div class="border-b border-gray-700/50 px-4 py-3 text-sm text-slate-300">
          <div class="mb-3 grid grid-cols-3 gap-2">
            <button
              v-for="gate in gates"
              :key="gate.assetType"
              :data-test="gate.dataTest"
              type="button"
              @click="selectGate(gate.assetType)"
              class="rounded border px-2 py-2 text-xs"
              :class="activeGate === gate.assetType ? 'border-sky-400 bg-sky-950/50 text-sky-100' : 'border-slate-700 bg-slate-950/40 text-slate-400 hover:border-slate-500'"
            >
              {{ gate.label }} {{ gateCounts[gate.assetType] || 0 }}
            </button>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span>待审查：{{ items.length }}</span>
            <span class="text-xs text-slate-500">已选 {{ selectedIds.length }} 个</span>
          </div>
          <div v-if="showBulkApprove" class="mt-3 flex items-center gap-2">
            <button
              data-test="bulk-approve"
              @click="bulkApprove"
              :disabled="acting || !bulkApprovableSelectedIds.length"
              class="rounded bg-emerald-600 px-3 py-2 text-xs text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              批量通过
            </button>
          </div>
          <div v-if="bulkResult" class="mt-2 text-xs text-slate-500">
            已通过 {{ bulkResult.approved || 0 }} 个，跳过过期 {{ bulkResult.skipped_stale || 0 }} 个。
          </div>
        </div>
        <div
          v-for="item in items"
          :key="item.id"
          class="flex border-b border-gray-800/60 hover:bg-slate-800/60"
          :class="selected?.id === item.id ? 'bg-slate-800/80' : ''"
        >
          <label class="flex items-center px-3 py-3">
            <input
              v-model="selectedIds"
              type="checkbox"
              :value="item.id"
              :aria-label="`选择 ${item.frame_id}`"
              :disabled="cannotApprove(item)"
              class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500"
              @click.stop
            />
          </label>
          <button @click="selected = item" class="min-w-0 flex-1 px-1 py-3 pr-4 text-left">
            <div class="text-sm text-slate-100">{{ item.frame_id }}</div>
            <div class="text-xs text-slate-500">v{{ item.version }} · {{ item.status }} · {{ item.stage }}</div>
          </button>
        </div>
        <div v-if="!items.length" class="px-4 py-10 text-center text-sm text-slate-500">
          暂无需要人工审查的素材。
        </div>
      </aside>

      <section class="min-h-[520px] rounded-xl border border-gray-700/50 p-5" style="background: rgba(15, 23, 42, 0.55);">
        <template v-if="selected">
          <div class="mb-4 flex justify-between gap-4">
            <div>
              <h2 class="text-lg font-semibold text-slate-100">{{ selected.frame_id }}</h2>
              <p class="mt-1 text-sm text-slate-400">{{ selectedGateCopy }}</p>
              <p class="text-xs text-slate-500">素材 {{ selected.id }}</p>
            </div>
            <span class="h-fit rounded bg-amber-900/40 px-2 py-1 text-xs text-amber-300">{{ selected.status }}</span>
          </div>

          <div class="mb-4 flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-gray-700/50 bg-slate-950/80">
            <video v-if="selected.asset_type !== 'image' && selectedPreviewUrl" :src="selectedPreviewUrl" controls class="max-h-full max-w-full"></video>
            <img v-else-if="selectedPreviewUrl" :src="selectedPreviewUrl" :alt="selected.frame_id" class="max-h-full max-w-full object-contain" />
            <span v-else class="text-sm text-slate-500">暂无预览 URL</span>
          </div>

          <div class="mb-5 grid grid-cols-1 gap-3 text-sm lg:grid-cols-3">
            <section class="rounded-lg border border-gray-700/50 bg-slate-950/40 p-3">
              <h3 class="mb-2 font-medium text-slate-200">分镜</h3>
              <p class="whitespace-pre-wrap text-slate-400">{{ selected.storyboard_frame?.image_prompt || '暂无提示词' }}</p>
              <p class="mt-2 whitespace-pre-wrap text-slate-500">{{ selected.storyboard_frame?.narration || '暂无旁白' }}</p>
              <div class="mt-2 break-all text-xs text-slate-500">
                <div v-for="url in selected.storyboard_frame?.reference_urls || []" :key="url">{{ url }}</div>
              </div>
            </section>
            <section class="rounded-lg border border-gray-700/50 bg-slate-950/40 p-3">
              <h3 class="mb-2 font-medium text-slate-200">AI 审查</h3>
              <p class="text-slate-400">状态：{{ selected.latest_ai_review?.status || 'none' }}</p>
              <p class="text-slate-400">评分：{{ selected.latest_ai_review?.score ?? '-' }}</p>
              <ul class="mt-2 space-y-1 text-xs text-amber-300">
                <li v-for="issue in selected.latest_ai_review?.issues_json || []" :key="issue">{{ issue }}</li>
              </ul>
            </section>
            <section class="rounded-lg border border-gray-700/50 bg-slate-950/40 p-3">
              <h3 class="mb-2 font-medium text-slate-200">模型追踪</h3>
              <pre class="whitespace-pre-wrap text-xs text-slate-400">{{ JSON.stringify(selected.model_trace_json || {}, null, 2) }}</pre>
            </section>
            <section class="rounded-lg border border-gray-700/50 bg-slate-950/40 p-3">
              <h3 class="mb-2 font-medium text-slate-200">参考图依据</h3>
              <div v-if="selectedReferenceUrls.length" class="grid grid-cols-2 gap-2">
                <a
                  v-for="url in selectedReferenceUrls"
                  :key="url"
                  :href="url"
                  target="_blank"
                  rel="noreferrer"
                  class="block overflow-hidden rounded border border-slate-800 bg-slate-950"
                >
                  <img :src="url" alt="参考图" class="h-20 w-full object-contain" />
                  <div class="truncate px-2 py-1 text-xs text-slate-500">{{ url }}</div>
                </a>
              </div>
              <p v-else class="text-xs text-slate-500">当前素材没有记录参考图依据。</p>
              <dl class="mt-3 space-y-1 text-xs text-slate-500">
                <div v-if="selected.reference_evidence?.scene_id">
                  <dt class="inline text-slate-400">场景：</dt>
                  <dd class="inline">{{ selected.reference_evidence.scene_id }}</dd>
                </div>
                <div v-if="selected.reference_evidence?.character_ids?.length">
                  <dt class="inline text-slate-400">角色：</dt>
                  <dd class="inline">{{ selected.reference_evidence.character_ids.join(', ') }}</dd>
                </div>
                <div v-if="selectedCharacterReferenceUrls.length">
                  <dt class="text-slate-400">角色参考：</dt>
                  <dd class="break-all">{{ selectedCharacterReferenceUrls.join(', ') }}</dd>
                </div>
                <div v-if="selectedStyleReferenceUrls.length">
                  <dt class="text-slate-400">风格参考：</dt>
                  <dd class="break-all">{{ selectedStyleReferenceUrls.join(', ') }}</dd>
                </div>
              </dl>
            </section>
          </div>

          <dl class="mb-5 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt class="text-slate-500">运行</dt>
              <dd class="font-mono text-slate-200">{{ selected.run_id }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">版本</dt>
              <dd class="text-slate-200">v{{ selected.version }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">本地路径</dt>
              <dd class="break-all text-slate-200">{{ selected.local_path || '未提供' }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Pixelle 任务</dt>
              <dd class="break-all text-slate-200">{{ selected.pixelle_task_id || '未提供' }}</dd>
            </div>
          </dl>

          <div v-if="approvalDisabledReason(selected)" data-test="approval-disabled-reason" class="mb-4 rounded-lg border border-amber-500/40 bg-amber-950/30 p-3 text-sm text-amber-100">
            {{ approvalDisabledReason(selected) }}
          </div>

          <div v-if="isStorageFailed(selected)" class="mb-4 rounded-lg border border-rose-500/40 bg-rose-950/30 p-3 text-sm text-rose-100">
            <div>{{ storageFailureMessage(selected) }}</div>
            <button
              data-test="retry-asset-persistence"
              type="button"
              @click="retryPersist"
              :disabled="acting"
              class="mt-3 cursor-pointer rounded-lg bg-rose-600 px-3 py-2 text-xs text-white hover:bg-rose-500 disabled:opacity-50"
            >
              重试资产持久化
            </button>
          </div>

          <div class="flex gap-2">
            <button data-test="approve-asset" @click="approve" :disabled="acting || cannotApprove(selected)" class="cursor-pointer rounded-lg bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-500 disabled:opacity-50">
              {{ selected.asset_type === 'final_video' ? '终审通过并入库' : '通过当前版本' }}
            </button>
            <button @click="reject" :disabled="acting" class="cursor-pointer rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-500 disabled:opacity-50">
              驳回
            </button>
            <button
              v-if="selected.asset_type !== 'final_video' && selected.status !== 'regenerating'"
              @click="regenerate"
              :disabled="acting"
              class="cursor-pointer rounded-lg bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 disabled:opacity-50"
            >
              重新生成
            </button>
            <button
              v-if="selected.asset_type !== 'final_video' && selected.status === 'regenerating'"
              @click="syncRegen"
              :disabled="acting"
              class="cursor-pointer rounded-lg bg-amber-600 px-4 py-2 text-sm text-white hover:bg-amber-500 disabled:opacity-50"
            >
              同步重生成
            </button>
            <button
              v-if="selected.asset_type === 'image'"
              data-test="open-image-edit"
              @click="openImageEdit"
              :disabled="acting"
              class="cursor-pointer rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              改图/重绘
            </button>
            <button
              @click="voidCurrentAsset"
              :disabled="acting"
              class="cursor-pointer rounded-lg border border-rose-700 px-4 py-2 text-sm text-rose-200 hover:bg-rose-950/40 disabled:opacity-50"
            >
              作废当前版本
            </button>
          </div>
        </template>
        <div v-else class="py-24 text-center text-slate-500">
          请选择一个素材进行审查。
        </div>
      </section>
    </div>

    <div v-if="imageEditOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="closeImageEdit">
      <section class="w-full max-w-lg rounded-lg border border-slate-800 bg-slate-950 p-5">
        <h2 class="text-lg font-semibold text-slate-100">改图/重绘</h2>
        <p class="mt-2 text-sm text-slate-400">系统会基于当前图片、分镜提示词和参考图生成新版本，不覆盖旧版本。</p>
        <div v-if="imageEditError" class="mt-4 rounded border border-red-500/40 bg-red-950/30 p-3 text-sm text-red-100">
          {{ imageEditError }}
        </div>
        <textarea
          data-test="image-edit-instruction"
          v-model="imageEditInstruction"
          rows="4"
          class="mt-4 w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
          placeholder="例如：保持发型和服装不变，修正脸部一致性"
        />
        <div class="mt-4 flex justify-end gap-2">
          <button type="button" class="rounded border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800" @click="closeImageEdit">取消</button>
          <button
            data-test="submit-image-edit"
            type="button"
            class="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="acting || !imageEditInstruction.trim()"
            @click="submitImageEdit"
          >
            生成新版本
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getVideoProductionRun,
  listReviewItems,
  reviewAsset,
  bulkReviewProductionAssets,
  retryAssetPersistence,
  startAssetRegeneration,
  syncAssetRegeneration,
  syncImageStage,
  runRealWorkerStep,
  imageEditProductionAsset,
  voidProductionAsset,
} from '../api/videoProduction.js'
import { authorizeAgencyRepairRetry, listAgencyRepairTasks, retryAgencyRepairTask } from '../api/agency.js'
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'
import AutoRepairTaskList from '../components/agency/AutoRepairTaskList.vue'

const route = useRoute()
const router = useRouter()
const items = ref([])
const selected = ref(null)
const selectedIds = ref([])
const loading = ref(true)
const acting = ref(false)
const syncing = ref(false)
const error = ref('')
const notice = ref('')
const bulkResult = ref(null)
const imageEditOpen = ref(false)
const imageEditInstruction = ref('')
const imageEditError = ref('')
const runId = ref(route.query.run_id || null)
const runStatus = ref(null)
const runType = ref(null)
const repairTasks = ref([])
const repairSummary = ref({})
const repairLoading = ref(false)
const repairError = ref('')
const repairBusyId = ref('')
const activeGate = ref(route.query.asset_type || '')
const gateCounts = ref({ image: 0, video_segment: 0, final_video: 0 })
const defaultReviewStatuses = ['review_pending', 'regenerating', 'failed', 'rejected'].join(',')
const gates = [
  { assetType: 'image', label: '图像审查', dataTest: 'gate-tab-image' },
  { assetType: 'video_segment', label: '视频片段审查', dataTest: 'gate-tab-video-segment' },
  { assetType: 'final_video', label: '最终审查', dataTest: 'gate-tab-final-video' },
]
const hasFinalVideoItem = computed(() => items.value.some(item => item.asset_type === 'final_video'))
const isRealShortRun = computed(() => runType.value === 'real_short_e2e')
const syncButtonText = computed(() => {
  if (syncing.value) return isRealShortRun.value ? '正在推进真实任务...' : '正在同步结果...'
  return isRealShortRun.value ? '推进真实任务' : '同步结果'
})
const bulkApprovableSelectedIds = computed(() => {
  const itemById = new Map(items.value.map(item => [item.id, item]))
  return selectedIds.value.filter(id => {
    const item = itemById.get(id)
    return item && !cannotApprove(item)
  })
})
const showBulkApprove = computed(() =>
  runType.value === 'mock_series_scale' &&
  activeGate.value !== 'final_video' &&
  !hasFinalVideoItem.value
)
const selectedGateCopy = computed(() => {
  if (activeGate.value === 'final_video' || selected.value?.asset_type === 'final_video') return '最终人工审查'
  if (activeGate.value === 'video_segment') return '视频片段审查'
  return '图像审查'
})
const selectedPreviewUrl = computed(() => safeReferenceUrl(selected.value?.url))
const selectedReferenceUrls = computed(() => {
  const evidence = selected.value?.reference_evidence || {}
  return uniqueSafeUrls([
    ...(evidence.reference_urls || []),
    ...(evidence.character_reference_urls || []),
    ...(evidence.style_reference_urls || []),
  ])
})
const selectedCharacterReferenceUrls = computed(() => uniqueSafeUrls(selected.value?.reference_evidence?.character_reference_urls || []))
const selectedStyleReferenceUrls = computed(() => uniqueSafeUrls(selected.value?.reference_evidence?.style_reference_urls || []))

function uniqueSafeUrls(values) {
  return [...new Set(values.map(safeReferenceUrl).filter(Boolean))]
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

function readableError(e, fallback) {
  const detail = e.response?.data?.detail
  return detail?.message || detail || e.message || fallback
}

function staleAssetId(e) {
  const detail = e.response?.data?.detail
  const code = detail?.code || e.response?.data?.code || ''
  const normalizedCode = String(code).toUpperCase()
  const isStale = normalizedCode === 'STALE_ASSET_VERSION' ||
    normalizedCode === 'ASSET_VERSION_CONFLICT' ||
    normalizedCode === 'STALE_VERSION' ||
    (normalizedCode.includes('STALE') && normalizedCode.includes('VERSION'))
  if (!isStale) return ''
  return detail?.current_asset_id || detail?.latest_asset_id || detail?.asset_id || ''
}

async function refreshAfterStaleVersion(e) {
  const preferredId = staleAssetId(e)
  if (!preferredId && !isStaleVersionError(e)) return false
  notice.value = '版本已过期，已刷新当前最新版本，请确认后重试。'
  await load(preferredId)
  return true
}

function isStaleVersionError(e) {
  const detail = e.response?.data?.detail
  const code = detail?.code || e.response?.data?.code || ''
  const normalizedCode = String(code).toUpperCase()
  return normalizedCode === 'STALE_ASSET_VERSION' ||
    normalizedCode === 'ASSET_VERSION_CONFLICT' ||
    normalizedCode === 'STALE_VERSION' ||
    (normalizedCode.includes('STALE') && normalizedCode.includes('VERSION'))
}

function cannotApprove(asset) {
  if (!asset) return true
  return (
    asset.copy_status !== 'persisted' ||
    !asset.checksum ||
    !asset.storage_path ||
    asset.status !== 'review_pending' ||
    asset.permission?.can_approve === false
  )
}

function approvalDisabledReason(asset) {
  if (!asset) return ''
  if (asset.copy_status !== 'persisted' || !asset.checksum || !asset.storage_path) return '资产尚未持久化'
  if (asset.copy_status !== 'persisted') return '资产尚未持久化'
  if (asset.status === 'superseded') return '旧版本不能审批'
  if (asset.status !== 'review_pending') return '资产不在待审查状态'
  if (asset.permission?.can_approve === false) return '当前账号没有审批权限'
  return ''
}

function isStorageFailed(asset) {
  return asset?.copy_status === 'storage_failed' || asset?.status === 'storage_failed'
}

function storageFailureMessage(asset) {
  return asset?.storage_error_json?.message || asset?.storage_error_json?.cause || '资产持久化失败'
}

async function load(preferredAssetId = '') {
  loading.value = true
  error.value = ''
  try {
    const params = {
      run_id: route.query.run_id || undefined,
      statuses: route.query.statuses || route.query.status || defaultReviewStatuses,
    }
    if (activeGate.value) params.asset_type = activeGate.value
    const { data } = await listReviewItems(params)
    items.value = data.ok ? data.items || [] : []
    gateCounts.value = data.gate_counts || gateCounts.value
    selected.value =
      items.value.find(item => item.id === preferredAssetId) ||
      items.value.find(item => item.id === route.query.asset_id) ||
      items.value[0] ||
      null
    const itemIds = new Set(items.value.map(item => item.id))
    selectedIds.value = selectedIds.value.filter(id => itemIds.has(id))
    await loadRepairTasks()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载审查队列失败'
  } finally {
    loading.value = false
  }
}

async function loadRepairTasks() {
  if (!runId.value) return
  repairLoading.value = true
  repairError.value = ''
  try {
    const { data } = await listAgencyRepairTasks({ run_id: runId.value })
    repairTasks.value = data.items || []
    repairSummary.value = data.summary || {}
  } catch (e) {
    repairTasks.value = []
    repairSummary.value = {}
    repairError.value = readableError(e, '返修任务加载失败，请稍后重试')
  } finally {
    repairLoading.value = false
  }
}

function openRepairAction(task) {
  if (task?.repair_route) window.location.href = task.repair_route
}

async function retryRepairTask(task, authorizationPayload = null) {
  if (!task?.id || repairBusyId.value) return
  repairBusyId.value = task.id
  repairError.value = ''
  try {
    if (task.retry_actions?.paid_authorization_required) {
      await authorizeAgencyRepairRetry(task.id, authorizationPayload || {
        reason: '人工确认追加自动返修预算',
        budget_delta: Number(task.estimated_cost || 0),
        confirmed_budget_delta: Number(task.estimated_cost || 0),
      })
    } else {
      await retryAgencyRepairTask(task.id)
    }
    await loadRepairTasks()
  } catch (e) {
    repairError.value = readableError(e, '返修重试失败，请稍后重试')
  } finally {
    repairBusyId.value = ''
  }
}

function openImageEdit() {
  imageEditOpen.value = true
  imageEditError.value = ''
}

function closeImageEdit() {
  imageEditOpen.value = false
  imageEditError.value = ''
}

async function submitImageEdit() {
  if (!selected.value) return
  const instruction = imageEditInstruction.value.trim()
  if (!instruction) return
  acting.value = true
  imageEditError.value = ''
  notice.value = ''
  try {
    const response = await imageEditProductionAsset(selected.value.id, {
      instruction,
      expected_version: selected.value.version,
    })
    const message = response.data?.message || (response.status === 202 || response.data?.status === 'pending'
      ? '改图任务已提交，等待生成结果同步。'
      : '改图任务已提交。')
    imageEditOpen.value = false
    imageEditInstruction.value = ''
    notice.value = message
    await load(response.data?.asset?.id || '')
  } catch (e) {
    if (await refreshAfterStaleVersion(e)) {
      imageEditError.value = '版本已过期，已刷新当前最新版本，请确认后重试。'
      return
    }
    imageEditError.value = readableError(e, '改图失败')
  } finally {
    acting.value = false
  }
}

async function voidCurrentAsset() {
  if (!selected.value) return
  const comment = prompt('作废原因（可选）：')
  if (comment === null) return
  acting.value = true
  error.value = ''
  notice.value = ''
  try {
    await voidProductionAsset(selected.value.id, {
      comment,
      expected_version: selected.value.version,
    })
    notice.value = '当前版本已作废。'
    await load()
  } catch (e) {
    if (await refreshAfterStaleVersion(e)) return
    error.value = readableError(e, '作废失败')
  } finally {
    acting.value = false
  }
}

async function selectGate(assetType) {
  activeGate.value = assetType
  selectedIds.value = []
  await router.push({
    query: {
      ...route.query,
      asset_type: assetType,
    },
  })
  await load()
}

async function approve() {
  if (!selected.value) return
  if (cannotApprove(selected.value)) return
  acting.value = true
  try {
    await reviewAsset(selected.value.id, 'approve', 'Approved from review center')
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '通过素材失败'
  } finally {
    acting.value = false
  }
}

async function retryPersist() {
  if (!selected.value || !isStorageFailed(selected.value)) return
  acting.value = true
  try {
    await retryAssetPersistence(selected.value.id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail?.message || e.response?.data?.detail || e.message || '重试资产持久化失败'
  } finally {
    acting.value = false
  }
}

async function bulkApprove() {
  if (!bulkApprovableSelectedIds.value.length) return
  acting.value = true
  error.value = ''
  try {
    const assetIds = [...bulkApprovableSelectedIds.value]
    const { data } = await bulkReviewProductionAssets({
      asset_ids: assetIds,
      action: 'approve',
      comment: 'Bulk approved from review center',
    })
    bulkResult.value = data.result || null
    selectedIds.value = []
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '批量通过失败'
  } finally {
    acting.value = false
  }
}

async function reject() {
  if (!selected.value) return
  const reason = prompt('驳回原因（可选）：')
  if (reason === null) return
  acting.value = true
  try {
    await reviewAsset(selected.value.id, 'reject', reason || 'Rejected from review center')
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '驳回素材失败'
  } finally {
    acting.value = false
  }
}

async function loadRunStatus() {
  if (!runId.value) return
  try {
    const { data } = await getVideoProductionRun(runId.value)
    if (data.ok) {
      runStatus.value = data.run.status
      runType.value = data.run.run_type || null
    }
  } catch (e) { /* ignore */ }
}

async function doSync() {
  if (!runId.value) return
  syncing.value = true
  error.value = ''
  try {
    if (isRealShortRun.value) {
      await runRealWorkerStep(runId.value)
    } else {
      await syncImageStage(runId.value)
    }
    await load()
    await loadRunStatus()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '同步失败'
  } finally {
    syncing.value = false
  }
}

async function regenerate() {
  if (!selected.value) return
  acting.value = true
  try {
    await startAssetRegeneration(selected.value.id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '启动重生成失败'
  } finally {
    acting.value = false
  }
}

async function syncRegen() {
  if (!selected.value) return
  acting.value = true
  try {
    await syncAssetRegeneration(selected.value.id)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '同步重生成失败'
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  await loadRunStatus()
  await load()
})
</script>
