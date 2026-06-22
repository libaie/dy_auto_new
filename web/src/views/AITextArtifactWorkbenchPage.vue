<!-- 管理端业务页面：承载 AITextArtifactWorkbenchPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="min-h-screen bg-slate-950 p-6 text-slate-100">
    <div class="mb-5 flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold">AI 文本追溯台</h1>
        <p class="mt-1 text-sm text-slate-400">查看 AI 输入、输出、模型 trace，并对文本产出进行人工编辑、批准或重新生成。</p>
      </div>
      <button class="rounded border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:bg-slate-900" @click="load">刷新</button>
    </div>

    <div v-if="loading" class="rounded border border-slate-800 bg-slate-900/70 p-6 text-slate-400">加载中...</div>
    <div v-else-if="error" class="rounded border border-red-500/40 bg-red-500/10 p-4 text-red-200">{{ error }}</div>
    <div v-else class="grid min-w-0 gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
      <aside class="min-w-0 rounded border border-slate-800 bg-slate-900/60">
        <div class="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">文本产物</div>
        <button
          v-for="artifact in artifacts"
          :key="artifact.id"
          class="block min-w-0 w-full border-b border-slate-800 px-4 py-3 text-left hover:bg-slate-800/70"
          :class="selectedArtifact?.id === artifact.id ? 'bg-slate-800' : ''"
          @click="selectArtifact(artifact)"
        >
          <div class="flex min-w-0 items-center justify-between gap-2 text-sm">
            <span class="min-w-0 truncate font-medium text-slate-100">{{ artifactListTitle(artifact) }}</span>
            <span class="rounded bg-slate-950 px-2 py-0.5 text-xs text-slate-300">v{{ artifact.version }}</span>
          </div>
          <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>{{ artifact.status }}</span>
            <span>{{ artifact.source_type }}</span>
            <span v-if="artifactTargetLabel(artifact)" class="text-cyan-400">{{ artifactTargetLabel(artifact) }}</span>
          </div>
        </button>
        <div v-if="!artifacts.length" class="px-4 py-6 text-sm text-slate-500">暂无 AI 文本产物</div>
      </aside>

      <main v-if="selectedArtifact" class="min-w-0 space-y-4">
        <section class="rounded border border-slate-800 bg-slate-900/60 p-4">
          <div class="mb-3 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-lg font-semibold">{{ selectedArtifact.artifact_type }} v{{ selectedArtifact.version }}</h2>
              <div class="mt-1 text-xs text-slate-500">
                {{ selectedArtifact.status }} · {{ selectedArtifact.source_type }}
                <span v-if="artifactTargetLabel(selectedArtifact)"> · {{ artifactTargetLabel(selectedArtifact) }}</span>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <button data-test="artifact-save-edit" class="rounded bg-cyan-600 px-3 py-2 text-sm text-white hover:bg-cyan-500" @click="saveEdit">保存人工编辑</button>
              <button data-test="artifact-regenerate" class="rounded bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-500" @click="regenerate">AI 重新生成</button>
              <button data-test="artifact-approve" class="rounded bg-emerald-600 px-3 py-2 text-sm text-white hover:bg-emerald-500" @click="approve">批准</button>
            </div>
          </div>
          <textarea
            data-test="artifact-edit-input"
            v-model="draftText"
            rows="12"
            class="w-full rounded border border-slate-700 bg-slate-950 p-3 font-mono text-sm text-slate-100"
          />
          <div class="mt-3 rounded border border-slate-800 bg-slate-950 p-3">
            <div class="mb-2 text-xs font-semibold uppercase text-slate-500">当前文本预览</div>
            <pre data-test="artifact-content-preview" class="whitespace-pre-wrap text-sm text-slate-200">{{ draftText }}</pre>
          </div>
          <div class="mt-3">
            <label class="mb-2 block text-xs font-semibold uppercase text-slate-500" for="artifact-regenerate-input">再生成要求</label>
            <textarea
              id="artifact-regenerate-input"
              data-test="artifact-regenerate-input"
              v-model="regenerateInstruction"
              rows="3"
              class="w-full rounded border border-slate-700 bg-slate-950 p-3 text-sm text-slate-100"
              placeholder="例如：增强结尾钩子，保持人物动机一致"
            />
          </div>
        </section>

        <section class="grid gap-4 xl:grid-cols-3">
          <div class="rounded border border-slate-800 bg-slate-900/60 p-4">
            <h3 class="mb-2 text-sm font-semibold text-slate-200">AI 输入</h3>
            <pre class="max-h-72 overflow-auto whitespace-pre-wrap text-xs text-slate-300">{{ formatJson(selectedArtifact.input_json) }}</pre>
          </div>
          <div class="rounded border border-slate-800 bg-slate-900/60 p-4">
            <h3 class="mb-2 text-sm font-semibold text-slate-200">结构化输出</h3>
            <pre class="max-h-72 overflow-auto whitespace-pre-wrap text-xs text-slate-300">{{ formatJson(selectedArtifact.content_json) }}</pre>
          </div>
          <div class="rounded border border-slate-800 bg-slate-900/60 p-4">
            <h3 class="mb-2 text-sm font-semibold text-slate-200">模型 Trace</h3>
            <pre class="max-h-72 overflow-auto whitespace-pre-wrap text-xs text-slate-300">{{ formatJson(selectedArtifact.model_trace_json) }}</pre>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  approveAITextArtifact,
  editAITextArtifact,
  listAITextArtifacts,
  regenerateAITextArtifact,
} from '../api/aiTextArtifacts.js'

const route = useRoute()
const artifacts = ref([])
const selectedArtifact = ref(null)
const draftText = ref('')
const regenerateInstruction = ref('')
const loading = ref(false)
const error = ref('')

// 前端业务函数：协调 formatJson 对应的页面流程、接口调用或状态转换。
// 入参：value 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 formatJson 对应业务流程的处理结果。
function formatJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

// 前端业务函数：协调 shortId 对应的页面流程、接口调用或状态转换。
// 入参：value 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 shortId 对应业务流程的处理结果。
function shortId(value) {
  return String(value || '').slice(0, 8)
}

// 前端业务函数：协调 artifactEpisodeNumber 对应的页面流程、接口调用或状态转换。
// 入参：artifact 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 artifactEpisodeNumber 对应业务流程的处理结果。
function artifactEpisodeNumber(artifact) {
  const content = artifact?.content_json || {}
  const input = artifact?.input_json || {}
  const numberValue = Number(content.episode_number || input.episode_number)
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : null
}

// 前端业务函数：协调 artifactEpisodeTitle 对应的页面流程、接口调用或状态转换。
// 入参：artifact 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 artifactEpisodeTitle 对应业务流程的处理结果。
function artifactEpisodeTitle(artifact) {
  const content = artifact?.content_json || {}
  const input = artifact?.input_json || {}
  return content.title || content.episode_title || input.title || input.episode_title || ''
}

// 前端业务函数：协调 artifactTargetLabel 对应的页面流程、接口调用或状态转换。
// 入参：artifact 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 artifactTargetLabel 对应业务流程的处理结果。
function artifactTargetLabel(artifact) {
  if (!artifact) return ''
  if (artifact.target_type === 'episode' || artifact.episode_id) {
    const episodeNumber = artifactEpisodeNumber(artifact)
    const title = artifactEpisodeTitle(artifact)
    const episodeLabel = episodeNumber ? `E${String(episodeNumber).padStart(2, '0')}` : ''
    if (episodeLabel && title) return `${episodeLabel} · ${title}`
    if (episodeLabel) return episodeLabel
    if (title) return title
    return artifact.episode_id ? `剧集 ${shortId(artifact.episode_id)}` : '剧集'
  }
  if (artifact.target_type === 'series') return '系列'
  if (artifact.target_type && artifact.target_id) return `${artifact.target_type} ${shortId(artifact.target_id)}`
  return ''
}

// 入参：artifact 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 artifactListTitle 对应业务流程的处理结果。
function artifactListTitle(artifact) {
  const target = artifactTargetLabel(artifact)
  return target ? `${artifact.artifact_type} · ${target}` : artifact.artifact_type
}

// 前端业务函数：协调 selectArtifact 对应的页面流程、接口调用或状态转换。
// 入参：artifact 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 selectArtifact 对应业务流程的处理结果。
function selectArtifact(artifact) {
  selectedArtifact.value = artifact
  draftText.value = artifact?.content_text || formatJson(artifact?.content_json)
  regenerateInstruction.value = ''
}

// 前端业务函数：协调 load 对应的页面流程、接口调用或状态转换。
// 入参：preferredArtifactId 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 load 对应业务流程的处理结果。
async function load(preferredArtifactId = '') {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listAITextArtifacts({
      series_id: route.params.seriesId,
      episode_id: route.query.episode_id,
    })
    artifacts.value = data.artifacts || []
    const preferred = preferredArtifactId
      ? artifacts.value.find((item) => item.id === preferredArtifactId)
      : null
    const current = selectedArtifact.value
      ? artifacts.value.find((item) => item.id === selectedArtifact.value.id)
      : null
    if (preferred) {
      selectArtifact(preferred)
    } else if (current) {
      selectArtifact(current)
    } else {
      selectArtifact(artifacts.value[0] || null)
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载 AI 文本产物失败'
  } finally {
    loading.value = false
  }
}

// 前端业务函数：协调 saveEdit 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 saveEdit 对应业务流程的处理结果。
async function saveEdit() {
  if (!selectedArtifact.value) return
  const { data } = await editAITextArtifact(selectedArtifact.value.id, {
    content_text: draftText.value,
    content_json: selectedArtifact.value.content_json || {},
  })
  await load(data?.artifact?.id)
}

// 前端业务函数：协调 approve 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 approve 对应业务流程的处理结果。
async function approve() {
  if (!selectedArtifact.value) return
  const { data } = await approveAITextArtifact(selectedArtifact.value.id)
  await load(data?.artifact?.id || selectedArtifact.value.id)
}

// 前端业务函数：协调 regenerate 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 regenerate 对应业务流程的处理结果。
async function regenerate() {
  if (!selectedArtifact.value) return
  const { data } = await regenerateAITextArtifact(selectedArtifact.value.id, {
    input_json: {
      reason: 'manual_regenerate_request',
      instruction: regenerateInstruction.value,
    },
  })
  await load(data?.artifact?.id)
}

onMounted(load)
</script>
