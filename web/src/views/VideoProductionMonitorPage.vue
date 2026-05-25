<template>
  <div class="p-6">
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">Video Production</h1>
        <p class="text-slate-500 text-sm font-mono mt-1">Run {{ runId }}</p>
      </div>
      <button @click="load" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg text-sm">Refresh</button>
    </div>

    <div v-if="loading" class="text-slate-400 py-12 text-center">Loading production run...</div>
    <div v-else-if="error" class="text-red-400 py-12 text-center">{{ error }}</div>
    <template v-else-if="run">
      <div class="grid grid-cols-7 gap-2 mb-6">
        <div v-for="step in steps" :key="step.key" class="rounded-lg border px-3 py-2 text-xs"
             :class="stepClass(step)">
          <div class="font-medium">{{ step.label }}</div>
          <div class="mt-1 opacity-70">{{ step.status }}</div>
        </div>
      </div>

      <div class="rounded-lg border border-gray-700/50 p-4 mb-6 bg-slate-900/50">
        <div class="text-sm text-slate-300">Current status: <span class="font-mono">{{ run.status }}</span></div>
        <div class="text-xs text-slate-500 mt-1">Current stage: {{ run.current_stage }}</div>
      </div>

      <div class="flex flex-wrap gap-2">
        <button v-if="run.status === 'image_batch_running'" @click="syncImages" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Sync Images</button>
        <button v-if="run.status === 'image_approved'" @click="startVideos" :disabled="acting" class="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Start Video Segments</button>
        <button v-if="run.status === 'video_batch_running'" @click="syncVideos" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Sync Video Segments</button>
        <button v-if="run.status === 'video_segments_approved'" @click="compose" :disabled="acting" class="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Compose Final Video</button>
        <button v-if="run.status === 'composing'" @click="syncCompose" :disabled="acting" class="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm">Sync Final Video</button>
        <button v-if="needsReview" @click="$router.push(`/ai-video-review?run_id=${run.id}`)" class="bg-orange-600 hover:bg-orange-500 text-white px-4 py-2 rounded-lg text-sm">Open Review Center</button>
      </div>

      <div class="mt-6 rounded-lg border border-gray-700/50 overflow-hidden">
        <div class="px-4 py-3 text-sm text-slate-300 border-b border-gray-700/50">Assets</div>
        <div v-for="asset in assets" :key="asset.id" class="px-4 py-3 text-sm flex gap-4 border-b border-gray-800/60">
          <span class="w-28 text-slate-400">{{ asset.asset_type }}</span>
          <span class="w-28 text-slate-400">{{ asset.frame_id }}</span>
          <span class="w-24" :class="asset.status === 'approved' ? 'text-emerald-400' : 'text-amber-300'">{{ asset.status }}</span>
          <span class="text-slate-500 truncate">{{ asset.url }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  getVideoProductionRun,
  syncImageStage,
  startVideoStage,
  syncVideoStage,
  startComposeStage,
  syncComposeStage,
} from '../api/videoProduction.js'

const route = useRoute()
const runId = route.params.runId
const run = ref(null)
const assets = ref([])
const loading = ref(true)
const acting = ref(false)
const error = ref('')

const needsReview = computed(() => ['image_review_pending', 'image_human_review_required', 'video_review_pending', 'video_human_review_required', 'final_review_pending'].includes(run.value?.status))

const steps = computed(() => [
  { key: 'storyboard', label: 'Storyboard', status: run.value?.storyboard_json?.frames?.length ? 'ready' : 'missing' },
  { key: 'images', label: 'Images', status: stageStatus(['image_batch_running', 'image_review_pending', 'image_human_review_required', 'image_approved']) },
  { key: 'img_review', label: 'Img Review', status: run.value?.status === 'image_approved' ? 'passed' : needsReview.value ? 'blocked' : 'pending' },
  { key: 'videos', label: 'Videos', status: stageStatus(['video_batch_running', 'video_review_pending', 'video_human_review_required', 'video_segments_approved']) },
  { key: 'vid_review', label: 'Vid Review', status: run.value?.status === 'video_segments_approved' ? 'passed' : 'pending' },
  { key: 'compose', label: 'Compose', status: stageStatus(['composing', 'completed']) },
  { key: 'done', label: 'Complete', status: run.value?.status === 'completed' ? 'done' : 'pending' },
])

function stageStatus(statuses) { return statuses.includes(run.value?.status) ? run.value.status : 'pending' }

function stepClass(step) {
  if (['passed', 'done', 'completed', 'image_approved', 'video_segments_approved'].includes(step.status)) return 'border-emerald-500/40 bg-emerald-950/30 text-emerald-300'
  if (['blocked', 'image_review_pending', 'image_human_review_required', 'video_review_pending', 'video_human_review_required'].includes(step.status)) return 'border-amber-500/40 bg-amber-950/30 text-amber-300'
  if (['image_batch_running', 'video_batch_running', 'composing'].includes(step.status)) return 'border-sky-500/40 bg-sky-950/30 text-sky-300'
  return 'border-gray-700/50 bg-slate-900/50 text-slate-500'
}

async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await getVideoProductionRun(runId)
    run.value = data.run; assets.value = data.assets || []
  } catch (e) { error.value = e.response?.data?.detail || e.message || 'Failed to load' } finally { loading.value = false }
}

async function act(fn) {
  acting.value = true; error.value = ''
  try { await fn(); await load() } catch (e) { error.value = e.response?.data?.detail || e.message || 'Action failed' } finally { acting.value = false }
}

function syncImages() { return act(() => syncImageStage(runId)) }
function startVideos() { return act(() => startVideoStage(runId)) }
function syncVideos() { return act(() => syncVideoStage(runId)) }
function compose() { return act(() => startComposeStage(runId)) }
function syncCompose() { return act(() => syncComposeStage(runId)) }

onMounted(load)
</script>
