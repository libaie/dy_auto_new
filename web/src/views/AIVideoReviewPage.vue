<template>
  <div class="p-6">
    <div class="flex justify-between items-start mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">AI Video Review</h1>
        <p class="text-slate-500 text-sm mt-1">Human decisions for staged video production assets.</p>
      </div>
      <div class="flex gap-2">
        <button v-if="runId && runStatus && (runStatus === 'image_batch_running' || runStatus === 'image_generation')"
                @click="doSync" :disabled="syncing"
                class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
          {{ syncing ? 'Syncing...' : 'Sync Pixelle Results' }}
        </button>
        <button @click="load" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
          Refresh
        </button>
      </div>
    </div>

    <div v-if="runId && runStatus" class="mb-4 px-4 py-2 rounded-lg text-sm"
         :class="runStatus === 'image_review_pending' ? 'bg-amber-900/30 text-amber-300' : 'bg-slate-800/40 text-slate-400'">
      Run status: {{ runStatus }}
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">Loading review queue...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else class="grid grid-cols-[320px_1fr] gap-4">
      <aside class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.55);">
        <div class="px-4 py-3 border-b border-gray-700/50 text-sm text-slate-300">
          Pending review: {{ items.length }}
        </div>
        <button
          v-for="item in items"
          :key="item.id"
          @click="selected = item"
          class="w-full text-left px-4 py-3 border-b border-gray-800/60 hover:bg-slate-800/60"
          :class="selected?.id === item.id ? 'bg-slate-800/80' : ''"
        >
          <div class="text-sm text-slate-100">{{ item.frame_id }}</div>
          <div class="text-xs text-slate-500">v{{ item.version }} · {{ item.status }} · {{ item.stage }}</div>
        </button>
        <div v-if="!items.length" class="px-4 py-10 text-center text-sm text-slate-500">
          No assets need human review.
        </div>
      </aside>

      <section class="rounded-xl border border-gray-700/50 p-5 min-h-[520px]" style="background: rgba(15, 23, 42, 0.55);">
        <template v-if="selected">
          <div class="flex justify-between gap-4 mb-4">
            <div>
              <h2 class="text-lg font-semibold text-slate-100">{{ selected.frame_id }}</h2>
              <p class="text-xs text-slate-500">Asset {{ selected.id }}</p>
            </div>
            <span class="px-2 py-1 rounded text-xs bg-amber-900/40 text-amber-300 h-fit">{{ selected.status }}</span>
          </div>

          <div class="aspect-video rounded-lg border border-gray-700/50 bg-slate-950/80 mb-4 overflow-hidden flex items-center justify-center">
            <video v-if="selected.asset_type !== 'image' && selected.url" :src="selected.url" controls class="max-h-full max-w-full"></video>
            <img v-else-if="selected.url" :src="selected.url" :alt="selected.frame_id" class="max-h-full max-w-full object-contain" />
            <span v-else class="text-sm text-slate-500">No preview URL</span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-5 text-sm">
            <section class="rounded-lg border border-gray-700/50 p-3 bg-slate-950/40">
              <h3 class="text-slate-200 font-medium mb-2">Storyboard</h3>
              <p class="text-slate-400 whitespace-pre-wrap">{{ selected.storyboard_frame?.image_prompt || 'No prompt' }}</p>
              <p class="text-slate-500 mt-2 whitespace-pre-wrap">{{ selected.storyboard_frame?.narration || 'No narration' }}</p>
              <div class="mt-2 text-xs text-slate-500 break-all">
                <div v-for="url in selected.storyboard_frame?.reference_urls || []" :key="url">{{ url }}</div>
              </div>
            </section>
            <section class="rounded-lg border border-gray-700/50 p-3 bg-slate-950/40">
              <h3 class="text-slate-200 font-medium mb-2">AI Review</h3>
              <p class="text-slate-400">Status: {{ selected.latest_ai_review?.status || 'none' }}</p>
              <p class="text-slate-400">Score: {{ selected.latest_ai_review?.score ?? '-' }}</p>
              <ul class="mt-2 text-xs text-amber-300 space-y-1">
                <li v-for="issue in selected.latest_ai_review?.issues_json || []" :key="issue">{{ issue }}</li>
              </ul>
            </section>
            <section class="rounded-lg border border-gray-700/50 p-3 bg-slate-950/40">
              <h3 class="text-slate-200 font-medium mb-2">Model Trace</h3>
              <pre class="text-xs text-slate-400 whitespace-pre-wrap">{{ JSON.stringify(selected.model_trace_json || {}, null, 2) }}</pre>
            </section>
          </div>

          <dl class="grid grid-cols-2 gap-3 text-sm mb-5">
            <div>
              <dt class="text-slate-500">Run</dt>
              <dd class="text-slate-200 font-mono">{{ selected.run_id }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Version</dt>
              <dd class="text-slate-200">v{{ selected.version }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Local path</dt>
              <dd class="text-slate-200 break-all">{{ selected.local_path || 'Not provided' }}</dd>
            </div>
            <div>
              <dt class="text-slate-500">Pixelle task</dt>
              <dd class="text-slate-200 break-all">{{ selected.pixelle_task_id || 'Not provided' }}</dd>
            </div>
          </dl>

          <div class="flex gap-2">
            <button @click="approve" :disabled="acting" class="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
              Approve latest
            </button>
            <button @click="reject" :disabled="acting" class="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
              Reject
            </button>
            <button v-if="selected.asset_type !== 'final_video'" @click="regenerate" :disabled="acting" class="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
              Regenerate
            </button>
            <button v-if="selected.asset_type !== 'final_video' && selected.status === 'regenerating'" @click="syncRegen" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm cursor-pointer">
              Sync Regeneration
            </button>
          </div>
        </template>
        <div v-else class="text-slate-500 text-center py-24">
          Select an asset to review.
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  getVideoProductionRun,
  listReviewItems,
  reviewAsset,
  startAssetRegeneration,
  syncAssetRegeneration,
  syncImageStage,
} from '../api/videoProduction.js'

const route = useRoute()
const items = ref([])
const selected = ref(null)
const loading = ref(true)
const acting = ref(false)
const syncing = ref(false)
const error = ref('')
const runId = ref(route.query.run_id || null)
const runStatus = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listReviewItems({
      run_id: route.query.run_id || undefined,
      status: route.query.status || 'review_pending',
    })
    items.value = data.ok ? data.items || [] : []
    selected.value = items.value.find(item => item.id === route.query.asset_id) || items.value[0] || null
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to load review queue'
  } finally {
    loading.value = false
  }
}

async function approve() {
  if (!selected.value) return
  acting.value = true
  try {
    await reviewAsset(selected.value.id, 'approve', 'Approved from review center')
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to approve asset'
  } finally {
    acting.value = false
  }
}

async function reject() {
  if (!selected.value) return
  const reason = prompt('Rejection reason (optional):')
  if (reason === null) return
  acting.value = true
  try {
    await reviewAsset(selected.value.id, 'reject', reason || 'Rejected from review center')
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to reject asset'
  } finally {
    acting.value = false
  }
}

async function loadRunStatus() {
  if (!runId.value) return
  try {
    const { data } = await getVideoProductionRun(runId.value)
    if (data.ok) runStatus.value = data.run.status
  } catch (e) { /* ignore */ }
}

async function doSync() {
  if (!runId.value) return
  syncing.value = true
  error.value = ''
  try {
    await syncImageStage(runId.value)
    await load()
    await loadRunStatus()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to sync Pixelle results'
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
    error.value = e.response?.data?.detail || e.message || 'Failed to start regeneration'
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
    error.value = e.response?.data?.detail || e.message || 'Failed to sync regeneration'
  } finally {
    acting.value = false
  }
}

onMounted(async () => {
  await loadRunStatus()
  await load()
})
</script>
