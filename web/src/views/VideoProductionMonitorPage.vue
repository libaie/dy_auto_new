<!-- 管理端业务页面：承载 VideoProductionMonitorPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="p-6 text-slate-100">
    <div class="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold">生产运行监控</h1>
        <p class="mt-1 font-mono text-sm text-slate-500">运行 {{ runId }}</p>
      </div>
      <button @click="load" class="rounded bg-sky-600 px-4 py-2 text-sm text-white hover:bg-sky-500">刷新</button>
    </div>

    <div v-if="loading" class="py-12 text-center text-slate-400">正在加载生产运行...</div>
    <div v-else-if="error" class="py-12 text-center text-red-400">{{ error }}</div>
    <template v-else>
      <section data-test="run-health-strip" aria-live="polite" class="mb-4 rounded border border-slate-800 bg-slate-950/70 p-4">
        <div class="mb-3 text-sm font-semibold text-slate-200">运行健康</div>
        <div class="grid grid-cols-2 gap-3 md:grid-cols-5">
          <div>
            <div class="text-xs uppercase text-slate-500">类型</div>
            <div class="mt-1 text-sm text-slate-100">{{ runTypeLabel }}</div>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500">状态</div>
            <div class="mt-1 font-mono text-sm text-slate-100">{{ run?.status || 'unknown' }}</div>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500">阶段</div>
            <div class="mt-1 font-mono text-sm text-slate-100">{{ run?.current_stage || 'draft' }}</div>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500">片段数</div>
            <div class="mt-1 font-mono text-sm text-slate-100">{{ tree?.total_segments ?? treeSegments.length }}</div>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500">成本</div>
            <div class="mt-1 font-mono text-sm text-slate-100">{{ formatCost(costs?.actual_cost ?? tree?.plan?.current_cost) }}</div>
          </div>
        </div>
      </section>

      <section data-test="consumed-text-artifacts" class="mb-4 rounded border border-slate-800 bg-slate-950/60 p-4">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div class="text-sm font-semibold text-slate-200">AI 文本版本</div>
          <div class="flex flex-wrap gap-2">
            <button
              v-if="run?.series_id"
              type="button"
              class="rounded border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-sky-500 hover:text-sky-200"
              @click="$router.push(`/series/${run.series_id}/ai-text-artifacts`)"
            >
              打开追溯台
            </button>
            <button
              v-if="!consumedTextArtifacts.length"
              data-test="backfill-text-artifacts"
              type="button"
              class="rounded bg-sky-600 px-3 py-2 text-xs text-white hover:bg-sky-500 disabled:opacity-50"
              :disabled="acting"
              @click="backfillTextArtifacts"
            >
              回填文字追溯
            </button>
          </div>
        </div>
        <div v-if="consumedTextArtifacts.length" class="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          <div v-for="artifact in consumedTextArtifacts" :key="artifact.consumer_id || artifact.artifact_id" class="rounded border border-slate-800 p-3 text-xs">
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-slate-100">{{ artifact.artifact_type }}</span>
              <span class="rounded border border-emerald-500/30 px-2 py-0.5 font-mono text-emerald-200">v{{ artifact.version }}</span>
            </div>
            <div class="mt-2 flex flex-wrap gap-2 text-slate-400">
              <span>{{ artifact.source_type || '-' }}</span>
              <span :class="statusClass(artifact.status)">{{ artifact.status || '-' }}</span>
            </div>
            <div class="mt-2 break-all font-mono text-slate-500">{{ artifact.artifact_id }}</div>
          </div>
        </div>
        <div v-else class="text-sm text-slate-500">暂无绑定的 AI 文本版本</div>
      </section>

      <section data-test="readiness-blocks" class="mb-4 rounded border border-slate-800 bg-slate-950/60 p-4">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-semibold text-slate-200">就绪状态</div>
            <div class="mt-1 text-sm text-slate-400">下一步：{{ readiness?.next_action?.label || '等待调度' }}</div>
          </div>
          <button
            v-if="nextRepairAction"
            data-test="next-repair-action"
            type="button"
            class="rounded bg-amber-600 px-3 py-2 text-xs text-white hover:bg-amber-500"
            @click="$router.push(nextRepairAction.route)"
          >
            {{ nextRepairAction.label }}
          </button>
        </div>
        <div v-if="readinessBlocks.length" class="space-y-2">
          <div v-for="block in readinessBlocks" :key="`${block.message}-${block.repair_route || ''}`" class="rounded border border-amber-500/30 bg-amber-950/20 p-3 text-sm text-amber-100">
            <div>{{ block.message }}</div>
            <div class="mt-1 text-xs text-amber-200/80">{{ block.repair_action }}</div>
            <div v-if="block.repair_route" class="mt-1 break-all font-mono text-xs text-amber-300">{{ block.repair_route }}</div>
          </div>
        </div>
        <div v-else class="text-sm text-slate-500">暂无阻塞项</div>
      </section>

      <section v-if="run?.episode_id" data-test="storyboard-image-readiness" class="mb-4 rounded border border-slate-800 bg-slate-950/60 p-4">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-semibold text-slate-200">分镜图</div>
            <div class="mt-1 flex flex-wrap gap-2 text-xs text-slate-400">
              <span>总数 {{ storyboardImageSummary.total || 0 }}</span>
              <span class="text-emerald-300">已通过 {{ storyboardImageSummary.approved || 0 }}</span>
              <span class="text-amber-300">待审 {{ storyboardImageSummary.pending || 0 }}</span>
              <span class="text-sky-300">生成中 {{ storyboardImageSummary.running || 0 }}</span>
              <span class="text-slate-500">缺失 {{ storyboardImageSummary.missing || 0 }}</span>
            </div>
          </div>
          <span v-if="storyboardImageError" class="text-xs text-rose-300">{{ storyboardImageError }}</span>
        </div>
        <div v-if="storyboardImageFrames.length" class="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          <div v-for="frame in storyboardImageFrames" :key="frame.frame_id" class="rounded border border-slate-800 p-3 text-xs">
            <div class="flex items-center justify-between gap-2">
              <span class="font-mono text-slate-200">{{ frame.time_range || frame.frame_id }}</span>
              <span :class="storyboardFrameImageStatusClass(frame.status)">{{ storyboardFrameImageStatusLabel(frame.status) }}</span>
            </div>
            <div class="mt-2 truncate text-slate-500">{{ frame.asset?.id || frame.task?.id || frame.frame_id }}</div>
            <button
              v-if="canPromoteStoryboardImage(frame)"
              :data-test="`promote-storyboard-image-${frame.asset.id}`"
              class="mt-3 rounded bg-sky-600 px-3 py-1.5 text-xs text-white hover:bg-sky-500 disabled:opacity-50"
              :disabled="acting || storyboardImagePromotingId === frame.asset.id"
              @click="promoteStoryboardFrameImage(frame)"
            >{{ storyboardImagePromotingId === frame.asset.id ? '处理中...' : '使用为首帧' }}</button>
          </div>
        </div>
        <div v-else class="text-sm text-slate-500">暂无分镜图状态</div>
      </section>

      <section v-if="readiness?.provider_throttle" data-test="provider-throttle" class="mb-4 rounded border border-amber-500/30 bg-amber-950/20 p-4">
        <div class="text-sm font-semibold text-amber-100">Provider 并发额度</div>
        <p class="mt-2 text-sm text-amber-100">当前 {{ readiness.provider_throttle.active_tasks ?? 0 }} / {{ readiness.provider_throttle.max_concurrent_tasks ?? '-' }}</p>
        <p v-if="readiness.provider_throttle.retry_after" class="mt-1 text-xs text-amber-200/80">下次重试：{{ readiness.provider_throttle.retry_after }}</p>
      </section>

      <div v-if="repairSummary.total || repairTasks.length || repairLoading || repairError" class="mb-4 space-y-3">
        <AutoRepairSummaryStrip :summary="repairSummary" />
        <AutoRepairTaskList
          :tasks="repairTasks"
          :loading="repairLoading"
          :error="repairError"
          :busy-id="repairBusyId"
          @manual-action="openRepairAction"
          @retry="retryRepair"
        />
      </div>

      <section v-if="costReservationRows.length" data-test="cost-reservations" class="mb-4 rounded border border-slate-800 bg-slate-950/60 p-4">
        <div class="mb-3 text-sm font-semibold text-slate-200">成本预留状态</div>
        <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div v-for="row in costReservationRows" :key="row.key" class="rounded border border-slate-800 p-3">
            <div class="text-xs text-slate-500">{{ row.label }}</div>
            <div class="mt-1 font-mono text-sm text-slate-100">{{ formatCost(row.value) }}</div>
          </div>
        </div>
      </section>

      <section v-if="storageFailedRows.length" data-test="asset-storage-failures" class="mb-4 rounded border border-rose-500/30 bg-rose-950/20 p-4">
        <div class="text-sm font-semibold text-rose-100">素材存储失败</div>
        <div class="mt-2 flex flex-wrap gap-2">
          <span v-for="row in storageFailedRows" :key="row.assetType" class="rounded border border-rose-500/30 px-2 py-1 text-xs text-rose-100">
            {{ assetTypeLabel(row.assetType) }} 存储失败 {{ row.count }}
          </span>
        </div>
      </section>

      <section data-test="stage-timeline" class="mb-4 grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
        <div v-for="step in steps" :key="step.key" class="rounded border px-3 py-2 text-xs" :class="stepClass(step)">
          <div class="font-medium">{{ step.label }}</div>
          <div class="mt-1 opacity-70">{{ step.status }}</div>
        </div>
      </section>

      <section data-test="exception-queue" class="mb-4 rounded border border-slate-800 bg-slate-950/60 p-4">
        <div class="mb-2 text-sm font-semibold text-slate-200">异常队列</div>
        <div v-if="exceptionSegments.length" class="flex flex-wrap gap-2">
          <button
            v-for="segment in exceptionSegments"
            :key="segment.id"
            type="button"
            @click="selectSegment(segment)"
            class="rounded border border-amber-500/40 bg-amber-950/30 px-3 py-1 text-xs text-amber-200"
          >
            {{ segment.segment_id || segment.id }} · {{ segment.status }}
          </button>
        </div>
        <div v-else class="text-sm text-slate-500">暂无阻塞异常</div>
      </section>

      <section v-if="providerStageTasks.length" data-test="provider-stage-tasks" class="mb-4 rounded border border-slate-800 bg-slate-950/60 p-4">
        <div class="mb-3 text-sm font-semibold text-slate-200">Provider 阶段任务</div>
        <div class="space-y-2">
          <div v-for="task in providerStageTasks" :key="task.id || `${task.stage}-${task.provider}-${task.status}`" class="grid gap-2 rounded border border-slate-800 p-3 text-xs text-slate-300 md:grid-cols-5">
            <span class="font-mono text-slate-100">{{ task.stage || '-' }}</span>
            <span>{{ task.provider || '-' }}</span>
            <span>{{ task.model_name || '-' }}</span>
            <span :class="statusClass(task.status)">{{ task.status || '-' }}</span>
            <span>{{ task.cost_reservation?.status || '-' }} {{ task.cost_reservation ? formatCost(task.cost_reservation.reserved_cost ?? task.cost_reservation.estimated_cost) : '' }}</span>
          </div>
        </div>
      </section>

      <div class="mb-4 flex flex-wrap items-center gap-2">
        <button data-test="primary-next-action" type="button" class="rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-60" :disabled="primaryAction.disabled" @click="primaryAction.run">
          {{ primaryAction.label }}
        </button>
        <button v-if="needsReview" @click="$router.push(`/ai-video-review?run_id=${run.id}`)" class="rounded bg-orange-600 px-4 py-2 text-sm text-white hover:bg-orange-500">打开审查中心</button>
      </div>

      <div data-test="developer-sync-controls" class="mb-6 flex flex-wrap gap-2 rounded border border-slate-800 bg-slate-950/50 p-3">
        <span class="mr-2 self-center text-xs uppercase text-slate-500">手动操作 / 模拟 worker</span>
        <button v-if="['draft', 'storyboard_ready'].includes(run?.status)" @click="startImages" :disabled="acting" class="rounded bg-sky-600 px-3 py-2 text-xs text-white hover:bg-sky-500 disabled:opacity-50">启动图片生成</button>
        <button v-if="run?.status === 'image_batch_running' && !isRealProviderRun" @click="syncImages" :disabled="acting" class="rounded bg-amber-600 px-3 py-2 text-xs text-white hover:bg-amber-500 disabled:opacity-50">同步图片结果</button>
        <button v-if="run?.status === 'image_approved'" @click="startVideos" :disabled="acting" class="rounded bg-cyan-600 px-3 py-2 text-xs text-white hover:bg-cyan-500 disabled:opacity-50">启动视频片段</button>
        <button v-if="run?.status === 'video_batch_running' && !isRealProviderRun" @click="syncVideos" :disabled="acting" class="rounded bg-amber-600 px-3 py-2 text-xs text-white hover:bg-amber-500 disabled:opacity-50">同步视频片段</button>
        <button v-if="run?.status === 'video_segments_approved'" @click="compose" :disabled="acting" class="rounded bg-emerald-600 px-3 py-2 text-xs text-white hover:bg-emerald-500 disabled:opacity-50">合成最终视频</button>
        <button v-if="run?.status === 'composing' && !isRealProviderRun" @click="syncCompose" :disabled="acting" class="rounded bg-amber-600 px-3 py-2 text-xs text-white hover:bg-amber-500 disabled:opacity-50">同步最终视频</button>
        <button v-if="isRealProviderRun && providerRunning" data-test="real-worker-step" @click="realWorkerStep" :disabled="acting" class="rounded bg-emerald-600 px-3 py-2 text-xs text-white hover:bg-emerald-500 disabled:opacity-50">运行真实 worker 一步</button>
        <button v-if="run?.run_type === 'mock_series_scale'" data-test="mock-worker-step" @click="mockWorkerStep" :disabled="acting" class="rounded bg-fuchsia-600 px-3 py-2 text-xs text-white hover:bg-fuchsia-500 disabled:opacity-50">手动操作：运行模拟 worker 一步</button>
      </div>

      <div data-test="control-room-grid" class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(260px,0.9fr)_minmax(360px,1.3fr)_minmax(260px,0.8fr)]">
        <section class="rounded border border-slate-800 bg-slate-950/60">
          <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">生产树</div>
          <div class="max-h-[560px] overflow-auto p-3">
            <div v-if="treeLoading" class="py-8 text-center text-sm text-slate-500">正在加载生产树...</div>
            <div v-else-if="treeError" class="py-8 text-center text-sm text-amber-300">{{ treeError }}</div>
            <div v-else-if="!treeSegments.length" class="py-8 text-center text-sm text-slate-500">暂无片段</div>
            <div v-for="episode in tree?.episodes || []" :key="episode.id" class="mb-4">
              <div class="mb-2 text-xs font-medium uppercase text-slate-500">集 {{ episode.order_index || episode.episode_id }}</div>
              <div v-for="scene in episode.scenes || []" :key="scene.id" class="mb-3 border-l border-slate-800 pl-3">
                <div class="mb-2 text-xs text-slate-400">{{ scene.scene_id }}</div>
                <div v-for="shot in scene.shots || []" :key="shot.id" class="mb-2">
                  <div class="mb-1 text-xs text-slate-500">{{ shot.shot_id }}</div>
                  <button
                    v-for="segment in shot.segments || []"
                    :key="segment.id"
                    data-test="segment-button"
                    type="button"
                    :aria-current="selectedSegment?.id === segment.id ? 'true' : undefined"
                    @click="selectSegment(segment)"
                    @keydown.enter.prevent="selectSegment(segment)"
                    @keydown.space.prevent="selectSegment(segment)"
                    class="mb-1 w-full rounded border px-3 py-2 text-left text-xs"
                    :class="selectedSegment?.id === segment.id ? 'border-sky-500 bg-sky-950/40 text-sky-200' : 'border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-600'"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-mono">{{ segment.segment_id || segment.id }}</span>
                      <span :class="statusClass(segment.status)">{{ segment.status }}</span>
                    </div>
                    <div class="mt-1 text-slate-500">{{ segment.duration_seconds || '-' }}s · v{{ segment.version || 1 }}</div>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="rounded border border-slate-800 bg-slate-950/60">
          <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">片段预览</div>
          <div v-if="selectedSegment" class="p-4">
            <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="font-mono text-lg text-slate-100">{{ selectedSegment.segment_id || selectedSegment.id }}</div>
                <div class="mt-1 text-sm text-slate-500">{{ selectedSegment.id }}</div>
              </div>
              <span class="rounded border border-slate-700 px-2 py-1 text-xs" :class="statusClass(selectedSegment.status)">{{ selectedSegment.status }}</span>
            </div>
            <div v-if="segmentDetailLoading" class="py-4 text-sm text-slate-500">正在加载片段详情...</div>
            <div v-else>
              <div v-if="segmentDetail?.repair" class="mb-4 rounded border border-amber-500/40 bg-amber-950/30 p-3 text-sm text-amber-200">
                {{ segmentDetail.repair.message }}
              </div>
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div class="rounded border border-slate-800 p-3">
                  <div class="text-xs uppercase text-slate-500">连续性</div>
                  <div class="mt-2 font-mono text-slate-200">{{ selectedSegment.continuity_mode || '-' }}</div>
                </div>
                <div class="rounded border border-slate-800 p-3">
                  <div class="text-xs uppercase text-slate-500">时长</div>
                  <div class="mt-2 font-mono text-slate-200">{{ selectedSegment.duration_seconds || '-' }}s</div>
                </div>
                <div class="rounded border border-slate-800 p-3">
                  <div class="text-xs uppercase text-slate-500">版本</div>
                  <div class="mt-2 font-mono text-slate-200">v{{ selectedSegment.version || 1 }}</div>
                </div>
                <div class="rounded border border-slate-800 p-3">
                  <div class="text-xs uppercase text-slate-500">允许操作</div>
                  <div class="mt-2 font-mono text-slate-200">{{ (segmentDetail?.allowed_actions || []).join(', ') || '-' }}</div>
                </div>
              </div>
              <div class="mt-4 rounded border border-slate-800 p-3">
                <div class="mb-2 text-xs uppercase text-slate-500">关联素材</div>
                <div v-for="asset in selectedAssets" :key="asset.id" class="flex gap-3 border-t border-slate-900 py-2 text-xs first:border-t-0">
                  <span class="w-24 text-slate-400">{{ asset.asset_type }}</span>
                  <span class="w-24" :class="statusClass(asset.status)">{{ asset.status }}</span>
                  <span class="truncate text-slate-500">{{ asset.url }}</span>
                </div>
                <div v-if="!selectedAssets.length" class="py-2 text-xs text-slate-500">暂无素材</div>
              </div>
            </div>
          </div>
          <div v-else class="p-8 text-center text-sm text-slate-500">未选择片段</div>
        </section>

        <section class="rounded border border-slate-800 bg-slate-950/60">
          <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">操作</div>
          <div class="space-y-4 p-4">
            <button
              data-test="retry-segment"
              @click="previewRetryImpact"
              :disabled="acting || !selectedSegment"
              class="w-full rounded bg-rose-600 px-4 py-2 text-sm text-white hover:bg-rose-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              重试片段
            </button>
            <div class="rounded border border-slate-800 p-3 text-xs text-slate-400">
              <div class="font-medium text-slate-300">审查关卡</div>
              <div class="mt-2">{{ needsReview ? '进入下一阶段前需要人工审查。' : '当前运行状态没有阻塞审查关卡。' }}</div>
            </div>
            <button v-if="needsReview" @click="$router.push(`/ai-video-review?run_id=${run.id}`)" class="w-full rounded border border-orange-500/50 px-4 py-2 text-sm text-orange-200 hover:bg-orange-950/40">打开审查中心</button>
          </div>
        </section>
      </div>

      <div data-test="mobile-action-bar" class="fixed inset-x-0 bottom-0 z-20 border-t border-slate-800 bg-slate-950/95 p-3 xl:hidden">
        <button type="button" class="w-full rounded bg-emerald-600 px-4 py-2 text-sm text-white disabled:opacity-60" :disabled="primaryAction.disabled" @click="primaryAction.run">
          {{ primaryAction.label }}
        </button>
      </div>

      <div v-if="retryDialogOpen" class="fixed inset-0 z-30 flex items-center justify-center bg-black/60 p-4">
        <div class="w-full max-w-md rounded border border-slate-700 bg-slate-950 p-5">
          <h2 class="text-lg font-semibold">重试影响</h2>
          <p class="mt-2 text-sm text-slate-400">预计额外成本：{{ formatCost(retryImpact?.estimated_extra_cost) }}</p>
          <div class="mt-4 flex justify-end gap-2">
            <button class="rounded border border-slate-700 px-3 py-2 text-sm text-slate-200" @click="retryDialogOpen = false">取消</button>
            <button class="rounded bg-rose-600 px-3 py-2 text-sm text-white" @click="confirmRetry">确认重试</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { listAgencyRepairTasks, retryAgencyRepairTask, authorizeAgencyRepairRetry } from '../api/agency.js'
import AutoRepairSummaryStrip from '../components/agency/AutoRepairSummaryStrip.vue'
import AutoRepairTaskList from '../components/agency/AutoRepairTaskList.vue'
import {
  getVideoProductionRun,
  getRunProductionTree,
  getRunReadiness,
  getSegmentDetail,
  getSegmentRetryImpact,
  getRunCosts,
  getProviderStageTasks,
  backfillRunTextArtifacts,
  retryProductionSegment,
  runMockSchedulerStep,
  runRealWorkerStep,
  startImageStage,
  syncImageStage,
  startVideoStage,
  syncVideoStage,
  startComposeStage,
  syncComposeStage,
} from '../api/videoProduction.js'
import { getStoryboardImageState, promoteStoryboardImageAsset } from '../api/storyboardImages.js'

const route = useRoute()
const runId = route.params.runId
const run = ref(null)
const tree = ref(null)
const readiness = ref(null)
const assetSummary = ref({})
const providerStageTasks = ref([])
const selectedSegment = ref(null)
const segmentDetail = ref(null)
const segmentDetailLoading = ref(false)
const costs = ref(null)
const retryImpact = ref(null)
const retryDialogOpen = ref(false)
const page = ref(1)
const statusFilter = ref('')
const loading = ref(true)
const treeLoading = ref(false)
const acting = ref(false)
const error = ref('')
const treeError = ref('')
const treePageSize = 50
const repairTasks = ref([])
const repairSummary = ref({})
const repairLoading = ref(false)
const repairError = ref('')
const repairBusyId = ref('')
const autopilotBusy = ref(false)
const autopilotTimer = ref(null)
const statusPollTimer = ref(null)
const storyboardImageState = ref(null)
const storyboardImageError = ref('')
const storyboardImagePromotingId = ref('')

const reviewStatuses = ['image_review_pending', 'image_human_review_required', 'video_review_pending', 'video_human_review_required', 'final_review_pending']
const statusPollStatuses = new Set(['reference_generation_running', 'image_batch_running', 'video_batch_running', 'composing'])
const STATUS_POLL_INTERVAL_MS = 5000
const needsReview = computed(() => reviewStatuses.includes(run.value?.status))
const providerRunning = computed(() => ['image_batch_running', 'video_batch_running', 'composing'].includes(run.value?.status))
const isRealProviderRun = computed(() => run.value?.run_type === 'real_short_e2e')
const autopilotEnabled = computed(() => {
  const trace = run.value?.model_trace_json || {}
  return trace.autopilot?.enabled === true || trace.one_sentence?.autostart_images_after_references === true
})
const runTypeLabels = {
  real_short_e2e: '真实短片',
  mock_series_scale: '模拟长剧调度',
  legacy: '历史剧集生产',
}
const runTypeLabel = computed(() => runTypeLabels[run.value?.run_type] || run.value?.run_type || '历史剧集生产')
const consumedTextArtifacts = computed(() => run.value?.consumed_text_artifacts || [])
const readinessBlocks = computed(() => readiness.value?.blocks || [])
const storyboardImageSummary = computed(() => storyboardImageState.value?.summary || {})
const storyboardImageFrames = computed(() => Array.isArray(storyboardImageState.value?.frames) ? storyboardImageState.value.frames : [])
const nextRepairAction = computed(() => {
  if (readiness.value?.next_repair_action) return readiness.value.next_repair_action
  const firstRepairBlock = readinessBlocks.value.find(block => block.repair_route)
  if (!firstRepairBlock) return null
  return {
    label: firstRepairBlock.repair_action || '打开修复入口',
    route: firstRepairBlock.repair_route,
  }
})
const costReservationRows = computed(() => {
  if (!costs.value) return []
  return [
    { key: 'active_reserved_cost', label: '活跃预留', value: costs.value.active_reserved_cost },
    { key: 'stale_needs_repair_cost', label: '待修复预留', value: costs.value.stale_needs_repair_cost },
    { key: 'settled_cost', label: '已结算', value: costs.value.settled_cost },
    { key: 'released_cost', label: '已释放', value: costs.value.released_cost },
  ].filter(row => row.value !== null && row.value !== undefined)
})
const storageFailedRows = computed(() => Object.entries(assetSummary.value || {})
  .map(([assetType, summary]) => ({
    assetType,
    count: Number(summary?.storage_failed || summary?.storageFailed || 0),
  }))
  .filter(row => row.count > 0))

const steps = computed(() => [
  { key: 'storyboard', label: '分镜', status: run.value?.storyboard_json?.frames?.length ? 'ready' : 'pending' },
  { key: 'images', label: '图片', status: stageStatus(['image_batch_running', 'image_review_pending', 'image_human_review_required', 'image_approved']) },
  { key: 'img_review', label: '图片审查', status: run.value?.status === 'image_approved' ? 'passed' : needsReview.value ? 'blocked' : 'pending' },
  { key: 'videos', label: '视频片段', status: stageStatus(['video_batch_running', 'video_review_pending', 'video_human_review_required', 'video_segments_approved']) },
  { key: 'vid_review', label: '片段审查', status: run.value?.status === 'video_segments_approved' ? 'passed' : 'pending' },
  { key: 'compose', label: '合成', status: stageStatus(['composing', 'completed']) },
  { key: 'done', label: '完成', status: run.value?.status === 'completed' ? 'done' : 'pending' },
])

const treeSegments = computed(() => flattenSegments(tree.value?.episodes || []))
const exceptionSegments = computed(() => treeSegments.value.filter(segment =>
  ['failed', 'failed_retryable', 'rejected', 'retry_queued'].includes(segment.status)
))
const selectedAssets = computed(() => {
  return Object.values(segmentDetail.value?.latest_assets || {}).filter(Boolean)
})
const primaryAction = computed(() => {
  if (providerRunning.value && isRealProviderRun.value) return { label: '运行真实 worker 一步', disabled: acting.value, run: realWorkerStep }
  if (providerRunning.value) return { label: '生成任务运行中', disabled: true, run: () => {} }
  if (['draft', 'storyboard_ready'].includes(run.value?.status)) return { label: '启动图片生成', disabled: acting.value, run: startImages }
  if (run.value?.status === 'image_approved') return { label: '启动视频片段', disabled: acting.value, run: startVideos }
  if (run.value?.status === 'video_segments_approved') return { label: '合成最终视频', disabled: acting.value, run: compose }
  if (needsReview.value) return { label: '需要审查', disabled: true, run: () => {} }
  if (run.value?.status === 'completed') return { label: '已完成', disabled: true, run: () => {} }
  return { label: '等待自动调度', disabled: true, run: () => {} }
})

function flattenSegments(episodes) {
  const rows = []
  for (const episode of episodes || []) {
    for (const scene of episode.scenes || []) {
      for (const shot of scene.shots || []) {
        rows.push(...(shot.segments || []))
      }
    }
  }
  return rows
}

function stageStatus(statuses) {
  return statuses.includes(run.value?.status) ? run.value.status : 'pending'
}

function stepClass(step) {
  if (['passed', 'done', 'completed', 'ready', 'image_approved', 'video_segments_approved'].includes(step.status)) return 'border-emerald-500/40 bg-emerald-950/30 text-emerald-300'
  if (['blocked', 'image_review_pending', 'image_human_review_required', 'video_review_pending', 'video_human_review_required'].includes(step.status)) return 'border-amber-500/40 bg-amber-950/30 text-amber-300'
  if (['image_batch_running', 'video_batch_running', 'composing'].includes(step.status)) return 'border-sky-500/40 bg-sky-950/30 text-sky-300'
  return 'border-slate-800 bg-slate-950/60 text-slate-500'
}

function statusClass(status) {
  if (['approved', 'completed', 'done', 'ready'].includes(status)) return 'text-emerald-300'
  if (['failed', 'rejected'].includes(status)) return 'text-rose-300'
  if (['review_pending', 'image_review_pending', 'video_review_pending', 'retry_queued', 'failed_retryable'].includes(status)) return 'text-amber-300'
  return 'text-slate-400'
}

function formatCost(value) {
  if (value === null || value === undefined) return '-'
  return Number(value).toFixed(2)
}

function assetTypeLabel(assetType) {
  return {
    image: '图像',
    video_segment: '视频片段',
    final_video: '最终视频',
  }[assetType] || assetType
}

function normalizeError(e) {
  const detail = e.response?.data?.detail
  if (detail && typeof detail === 'object') return detail
  return {
    error_code: 'UNKNOWN',
    message: detail || e.message || '操作失败',
    repair_action: '刷新',
    retryable: true,
    affected_ids: [],
  }
}

async function loadRunSummary() {
  const runResponse = await getVideoProductionRun(runId)
  run.value = runResponse.data.run
  assetSummary.value = runResponse.data.asset_summary || {}
}

async function loadReadiness() {
  try {
    const readinessResponse = await getRunReadiness(runId)
    readiness.value = readinessResponse.data?.readiness || readinessResponse.data
  } catch (e) {
    readiness.value = null
  }
}

async function loadCostSummary() {
  try {
    const costsResponse = await getRunCosts(runId)
    costs.value = costsResponse.data
  } catch (e) {
    costs.value = null
  }
}

async function loadProviderStageTasks(params = {}) {
  try {
    const { data } = await getProviderStageTasks(runId, {
      page: params.page ?? 1,
      page_size: params.page_size ?? treePageSize,
    })
    providerStageTasks.value = data.tasks || []
  } catch (e) {
    providerStageTasks.value = []
  }
}

async function loadRepairTasks() {
  repairLoading.value = true
  repairError.value = ''
  try {
    const { data } = await listAgencyRepairTasks({ run_id: runId, page: 1, page_size: 20 })
    repairTasks.value = data.items || []
    repairSummary.value = data.summary || {}
  } catch (e) {
    repairTasks.value = []
    repairSummary.value = {}
    repairError.value = '返修任务加载失败，请稍后重试'
  } finally {
    repairLoading.value = false
  }
}

async function loadStoryboardImages() {
  if (!run.value?.episode_id || !run.value?.series_id) {
    storyboardImageState.value = null
    return
  }
  try {
    const { data } = await getStoryboardImageState(run.value.episode_id, {
      series_id: run.value.series_id,
      run_id: run.value.id,
    })
    storyboardImageState.value = data?.ok ? data : null
    storyboardImageError.value = ''
  } catch (e) {
    storyboardImageState.value = null
    storyboardImageError.value = normalizeError(e).message || '分镜图状态加载失败'
  }
}

async function load(options = {}) {
  const silent = options.silent === true
  if (!silent) loading.value = true
  error.value = ''
  try {
    await Promise.all([
      loadRunSummary(),
      loadReadiness(),
      loadCostSummary(),
      loadProviderStageTasks({ page: 1, page_size: treePageSize }),
      loadTree({ page: 1, page_size: treePageSize }),
      loadRepairTasks(),
    ])
    await loadStoryboardImages()
    await refreshSelectedSegmentDetail({ silent })
  } catch (e) {
    const detail = normalizeError(e)
    error.value = detail.message
  } finally {
    if (!silent) loading.value = false
    scheduleStatusPoll()
    scheduleAutopilot()
  }
}

function storyboardFrameImageStatusLabel(status) {
  return {
    approved: '已通过',
    pending: '待审',
    running: '生成中',
    blocked: '已阻断',
    missing: '未生成',
  }[status || 'missing'] || '未生成'
}

function storyboardFrameImageStatusClass(status) {
  if (status === 'approved') return 'text-emerald-300'
  if (status === 'pending' || status === 'running') return 'text-amber-300'
  if (status === 'blocked') return 'text-rose-300'
  return 'text-slate-500'
}

function canPromoteStoryboardImage(frame) {
  return Array.isArray(frame?.asset?.allowed_actions) && frame.asset.allowed_actions.includes('promote_to_video_asset')
}

async function promoteStoryboardFrameImage(frame) {
  if (!frame?.asset?.id || !run.value?.id || !run.value?.episode_id) return
  storyboardImagePromotingId.value = frame.asset.id
  await act(async () => {
    await promoteStoryboardImageAsset(frame.asset.id, {
      run_id: run.value.id,
      frame_id: frame.frame_id,
      episode_id: run.value.episode_id,
      asset_version: frame.asset.version,
    })
  })
  storyboardImagePromotingId.value = ''
}

async function loadTree(params = {}) {
  treeLoading.value = true
  treeError.value = ''
  const nextPage = params.page ?? page.value
  const nextPageSize = params.page_size ?? treePageSize
  page.value = nextPage
  try {
    const treeResponse = await getRunProductionTree(runId, {
      page: nextPage,
      page_size: nextPageSize,
      status: statusFilter.value || undefined,
    })
    tree.value = treeResponse.data
    if (selectedSegment.value && !treeSegments.value.some(segment => segment.id === selectedSegment.value.id)) {
      selectedSegment.value = null
      segmentDetail.value = null
    }
  } catch (e) {
    tree.value = null
    selectedSegment.value = null
    segmentDetail.value = null
    treeError.value = normalizeError(e).message || '生产树不可用'
  } finally {
    treeLoading.value = false
  }
}

async function selectSegment(segment) {
  selectedSegment.value = segment
  await refreshSelectedSegmentDetail()
}

async function refreshSelectedSegmentDetail(options = {}) {
  if (!selectedSegment.value?.id) return
  const silent = options.silent === true
  if (!silent) segmentDetailLoading.value = true
  try {
    const { data } = await getSegmentDetail(selectedSegment.value.id, { history_limit: 10 })
    segmentDetail.value = data
  } catch (e) {
    segmentDetail.value = { repair: normalizeError(e) }
  } finally {
    if (!silent) segmentDetailLoading.value = false
  }
}

async function act(fn) {
  if (acting.value) return
  clearAutopilotTimer()
  clearStatusPollTimer()
  acting.value = true
  error.value = ''
  try {
    await fn()
    await load()
  } catch (e) {
    error.value = normalizeError(e).message
  } finally {
    acting.value = false
  }
}

function clearAutopilotTimer() {
  if (autopilotTimer.value) {
    clearTimeout(autopilotTimer.value)
    autopilotTimer.value = null
  }
}

function clearStatusPollTimer() {
  if (statusPollTimer.value) {
    clearTimeout(statusPollTimer.value)
    statusPollTimer.value = null
  }
}

function shouldPollStatus() {
  return Boolean(
    !autopilotEnabled.value
      && !acting.value
      && statusPollStatuses.has(run.value?.status),
  )
}

function scheduleStatusPoll(delay = STATUS_POLL_INTERVAL_MS) {
  clearStatusPollTimer()
  if (!shouldPollStatus()) return
  statusPollTimer.value = setTimeout(() => load({ silent: true }), delay)
}

function scheduleAutopilot(delay = 800) {
  clearAutopilotTimer()
  if (!autopilotEnabled.value || autopilotBusy.value || acting.value) return
  if (needsReview.value || ['completed', 'failed', 'blocked', 'reference_generation_blocked'].includes(run.value?.status)) return
  autopilotTimer.value = setTimeout(runAutopilotOnce, delay)
}

async function runAutopilotOnce() {
  if (!autopilotEnabled.value || autopilotBusy.value || acting.value) return
  autopilotBusy.value = true
  try {
    const status = run.value?.status
    if (status === 'reference_generation_running') {
      await load()
    } else if (['draft', 'storyboard_ready'].includes(status)) {
      await startImages()
    } else if (status === 'image_batch_running') {
      if (isRealProviderRun.value) await realWorkerStep()
      else await syncImages()
    } else if (status === 'image_approved') {
      await startVideos()
    } else if (status === 'video_batch_running') {
      if (isRealProviderRun.value) await realWorkerStep()
      else await syncVideos()
    } else if (status === 'video_segments_approved') {
      await compose()
    } else if (status === 'composing') {
      if (isRealProviderRun.value) await realWorkerStep()
      else await syncCompose()
    }
  } finally {
    autopilotBusy.value = false
    scheduleAutopilot(3000)
  }
}

function startImages() { return act(() => startImageStage(runId)) }
function backfillTextArtifacts() { return act(() => backfillRunTextArtifacts(runId)) }
function syncImages() { return act(() => syncImageStage(runId)) }
function startVideos() { return act(() => startVideoStage(runId)) }
function syncVideos() { return act(() => syncVideoStage(runId)) }
function compose() { return act(() => startComposeStage(runId)) }
function syncCompose() { return act(() => syncComposeStage(runId)) }
function realWorkerStep() { return act(() => runRealWorkerStep(runId, { lease_id: 'ui-real-worker', batch_size: 1, async_mode: true })) }
function mockWorkerStep() { return act(() => runMockSchedulerStep(runId, { lease_id: 'ui-worker', batch_size: 1 })) }

function openRepairAction(task) {
  if (task?.repair_route) {
    window.location.href = task.repair_route
  }
}

async function retryRepair(task, authorizationPayload = null) {
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
    repairError.value = normalizeError(e).message || '返修重试失败，请稍后重试'
  } finally {
    repairBusyId.value = ''
  }
}

async function previewRetryImpact() {
  if (acting.value || !selectedSegment.value) return
  try {
    const { data } = await getSegmentRetryImpact(selectedSegment.value.id)
    retryImpact.value = data
    retryDialogOpen.value = true
  } catch (e) {
    segmentDetail.value = { ...(segmentDetail.value || {}), repair: normalizeError(e) }
  }
}

async function confirmRetry() {
  if (!selectedSegment.value) return
  retryDialogOpen.value = false
  await act(() => retryProductionSegment(selectedSegment.value.id))
}

onMounted(load)
onBeforeUnmount(() => {
  clearAutopilotTimer()
  clearStatusPollTimer()
})
</script>
