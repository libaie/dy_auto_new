<!-- 管理端业务页面：承载 VideoStudio 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import SystemConfigPanel from '../components/video-studio/SystemConfigPanel.vue'
import ContentPanel from '../components/video-studio/ContentPanel.vue'
import VoiceVisualPanel from '../components/video-studio/VoiceVisualPanel.vue'
import GeneratePanel from '../components/video-studio/GeneratePanel.vue'
import CustomMediaPanel from '../components/video-studio/CustomMediaPanel.vue'
import DigitalHumanPanel from '../components/video-studio/DigitalHumanPanel.vue'
import ImageToVideoPanel from '../components/video-studio/ImageToVideoPanel.vue'
import ActionTransferPanel from '../components/video-studio/ActionTransferPanel.vue'
import SeedancePanel from '../components/video-studio/SeedancePanel.vue'
import {
  generateVideoAsync, getTask, listTemplates, getOpenAPISpec,
  listMediaWorkflows, listTTSWorkflows, listBGMs, getVideoFileUrl,
} from '../api/pixelle-client.js'
import { getPixelleConfig, updatePixelleConfig } from '../api/pixelle.js'
import { listCharacters } from '../api/characters.js'
import { listScenes } from '../api/scenes.js'
import PipelineLayerConfig from '../components/video-studio/PipelineLayerConfig.vue'
import { uploadPixelleFile } from '../components/video-studio/pixelleGeneration.js'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()

// ==================== Pipeline tabs ====================

const pipelines = [
  { key: 'quick_create', label: '快速创作', icon: 'M13 10V3L4 14h7v7l9-11h-7z', desc: 'AI 自动生成脚本→配图→配音→合成' },
  { key: 'custom_media', label: '自定义素材', icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z', desc: '上传图片/视频/音频素材，AI 生成视频' },
  { key: 'digital_human', label: '数字人口播', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z', desc: '数字人形象+配音，生成口播视频' },
  { key: 'image_to_video', label: '图生视频', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z', desc: '上传图片，AI 生成动态视频' },
  { key: 'action_transfer', label: '动作迁移', icon: 'M8 5v14l11-7z', desc: '上传视频，提取动作并迁移' },
  { key: 'seedance', label: 'Seedance 2.0', icon: 'M13 10V3L4 14h7v7l9-11h-7z', desc: '字节跳动 Seedance 2.0 原生视频生成 (1080P 声画同步)' },
]
const activePipeline = ref('quick_create')

// ==================== Layer Model Config ====================

const layerModels = ref({
  scriptLLM: 'qwen-max',
  imageModel: 'flux',
  videoModel: 'auto',
  ttsModel: 'edge-tts',
  auditModel: 'auto',
})

// ==================== Character & Scene Selection ====================

const characterList = ref([])
const sceneList = ref([])
const selectedCharacterIds = ref([])
const selectedSceneIds = ref([])

// 前端业务函数：协调 loadAssets 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 loadAssets 对应业务流程的处理结果。
async function loadAssets() {
  try {
    const [cRes, sRes] = await Promise.all([
      listCharacters().catch(() => ({ data: { ok: false, characters: [] } })),
      listScenes().catch(() => ({ data: { ok: false, scenes: [] } })),
    ])
    characterList.value = cRes.data.ok ? cRes.data.characters : []
    sceneList.value = sRes.data.ok ? sRes.data.scenes : []
  } catch {}
}

// 前端业务函数：协调 toggleCharacter 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 toggleCharacter 对应业务流程的处理结果。
function toggleCharacter(id) {
  const idx = selectedCharacterIds.value.indexOf(id)
  if (idx >= 0) selectedCharacterIds.value.splice(idx, 1)
  else selectedCharacterIds.value.push(id)
}

// 前端业务函数：协调 toggleScene 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 toggleScene 对应业务流程的处理结果。
function toggleScene(id) {
  const idx = selectedSceneIds.value.indexOf(id)
  if (idx >= 0) selectedSceneIds.value.splice(idx, 1)
  else selectedSceneIds.value.push(id)
}

// ==================== System Config ====================

const systemConfig = ref({
  llmApiKey: '',
  llmBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  llmModel: 'qwen-max',
  comfyuiUrl: 'http://127.0.0.1:8188',
  comfyuiApiKey: '',
  runninghubApiKey: '',
  runninghubConcurrent: 1,
  defaultTtsWorkflow: 'selfhost/tts_edge.json',
  defaultImageWorkflow: 'runninghub/image_flux.json',
  defaultVideoWorkflow: 'runninghub/video_wan2.1_fusionx.json',
  templateFontSize: '28px',
  templateTextColor: '#ffffff',
  templateBgColor: '#000000',
})

// 前端业务函数：协调 loadSystemConfig 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 loadSystemConfig 对应业务流程的处理结果。
async function loadSystemConfig() {
  try {
    const resp = await getPixelleConfig()
    const data = resp.data
    const cfg = systemConfig.value
    if (data.llm) {
      cfg.llmBaseUrl = data.llm.base_url || cfg.llmBaseUrl
      cfg.llmModel = data.llm.model || cfg.llmModel
    }
    if (data.comfyui) {
      cfg.comfyuiUrl = data.comfyui.comfyui_url || cfg.comfyuiUrl
      cfg.runninghubConcurrent = data.comfyui.runninghub_concurrent_limit || cfg.runninghubConcurrent
    }
    if (data.template) {
      const tpl = data.template.custom_params || {}
      if (tpl.font_size) cfg.templateFontSize = tpl.font_size
      if (tpl.text_color) cfg.templateTextColor = tpl.text_color
      if (tpl.background_color) cfg.templateBgColor = tpl.background_color
    }
  } catch { /* config.yaml may not exist yet */ }
}

// 前端业务函数：协调 buildPixelleConfigUpdates 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 buildPixelleConfigUpdates 对应业务流程的处理结果。
function buildPixelleConfigUpdates() {
  const cfg = systemConfig.value
  const updates = {
    llm: { base_url: cfg.llmBaseUrl, model: cfg.llmModel },
    comfyui: {
      comfyui_url: cfg.comfyuiUrl,
      runninghub_concurrent_limit: cfg.runninghubConcurrent,
    },
    template: {
      custom_params: {
        font_size: cfg.templateFontSize,
        text_color: cfg.templateTextColor,
        background_color: cfg.templateBgColor,
      },
    },
  }
  if (cfg.llmApiKey) updates.llm.api_key = cfg.llmApiKey
  if (cfg.comfyuiApiKey) updates.comfyui.comfyui_api_key = cfg.comfyuiApiKey
  if (cfg.runninghubApiKey) updates.comfyui.runninghub_api_key = cfg.runninghubApiKey
  return updates
}

let saveTimer = null
watch(systemConfig, () => {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try { await updatePixelleConfig(buildPixelleConfigUpdates()) } catch {}
  }, 1000)
}, { deep: true })

// ==================== Content Form ====================

const contentForm = ref({
  text: '',
  title: '',
  mode: 'generate',
  splitMode: 'paragraph',
  nScenes: 5,
  bgmMode: 'none',
  bgmId: 'calm_01',
  bgmVolume: 0.2,
  customBgmFile: null,
})

// ==================== Voice & Visual Form ====================

const voiceVisualForm = ref({
  ttsEngine: 'edge-tts',
  ttsVoice: 'zh-CN-XiaoxiaoNeural',
  ttsSpeed: 1.0,
  ttsWorkflow: 'selfhost/tts_edge.json',
  refAudioFile: null,
  mediaWorkflow: '',
  promptPrefix: '',
  frameTemplate: '',
})

// ==================== Templates / Workflows / BGM ====================

const templates = ref([])
const mediaWorkflows = ref([])
const ttsWorkflows = ref([])
const bgmList = ref([])
const resourcesLoading = ref(false)

// 前端业务函数：协调 fetchResources 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 fetchResources 对应业务流程的处理结果。
async function fetchResources() {
  resourcesLoading.value = true
  try {
    const [tRes, mRes, ttsRes, bgmRes] = await Promise.all([
      listTemplates().catch(() => ({ data: { templates: [] } })),
      listMediaWorkflows().catch(() => ({ data: { workflows: [] } })),
      listTTSWorkflows().catch(() => ({ data: { workflows: [] } })),
      listBGMs().catch(() => ({ data: { bgm_files: [] } })),
    ])
    templates.value = Array.isArray(tRes.data) ? tRes.data : (tRes.data.templates || [])
    mediaWorkflows.value = mRes.data?.workflows || []
    ttsWorkflows.value = ttsRes.data?.workflows || []
    bgmList.value = bgmRes.data?.bgm_files || []
  } catch {
    templates.value = [
      { key: '1080x1920/image_default.html', name: 'image_default.html', size: '1080x1920' },
      { key: '1920x1080/image_default.html', name: 'image_default.html', size: '1920x1080' },
      { key: '1080x1080/image_default.html', name: 'image_default.html', size: '1080x1080' },
    ]
  } finally {
    resourcesLoading.value = false
  }
}

// ==================== Generation State ====================

const generating = ref(false)
const progress = ref({ percent: 0, message: '', status: '' })
const result = ref(null)
const videoUrl = ref('')
const history = ref([])

let pollTimer = null

// ==================== Actions ====================

// 前端业务函数：协调 handleTestConnection 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleTestConnection 对应业务流程的处理结果。
async function handleTestConnection() {
  try {
    const resp = await getOpenAPISpec()
    toast.success(`Pixelle-Video 连接成功 (v${resp.data?.info?.version || '?'})`)
  } catch {
    toast.error('Pixelle-Video 连接失败，请检查服务是否启动')
  }
}

// 入参：event 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleBgmUpload 对应业务流程的处理结果。
function handleBgmUpload(event) {
  contentForm.value.customBgmFile = event.target.files?.[0] || null
}

// 前端业务函数：协调 handleRefAudioUpload 对应的页面流程、接口调用或状态转换。
// 入参：event 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleRefAudioUpload 对应业务流程的处理结果。
function handleRefAudioUpload(event) {
  voiceVisualForm.value.refAudioFile = event.target.files?.[0] || null
}

// 前端业务函数：协调 handleGenerate 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleGenerate 对应业务流程的处理结果。
async function handleGenerate() {
  const cf = contentForm.value
  if (!cf.text.trim()) { toast.error('请输入视频主题或脚本'); return }

  generating.value = true
  result.value = null
  videoUrl.value = ''
  progress.value = { percent: 0, message: '正在连接 Pixelle-Video...', status: '' }

  try {
    const vf = voiceVisualForm.value
    const payload = {
      text: cf.text,
      mode: cf.mode,
      n_scenes: cf.nScenes,
    }
    if (cf.title) payload.title = cf.title
    if (cf.mode === 'fixed') payload.split_mode = cf.splitMode
    if (vf.frameTemplate) payload.frame_template = vf.frameTemplate

    if (vf.ttsEngine === 'edge-tts') {
      payload.tts_voice = vf.ttsVoice
      if (vf.ttsSpeed !== 1.0) payload.tts_speed = vf.ttsSpeed
    } else if (vf.ttsEngine === 'custom') {
      payload.tts_workflow = vf.ttsWorkflow
    }
    if (vf.ttsWorkflow && vf.ttsEngine !== 'custom') payload.tts_workflow = vf.ttsWorkflow
    if (vf.mediaWorkflow) payload.media_workflow = vf.mediaWorkflow
    if (vf.promptPrefix) payload.prompt_prefix = vf.promptPrefix

    if (cf.bgmMode === 'builtin') {
      payload.bgm_path = cf.bgmId  // full path e.g. bgm/default.mp3
    } else if (cf.bgmMode === 'custom' && cf.customBgmFile) {
      progress.value.message = '正在上传自定义 BGM...'
      payload.bgm_path = await uploadPixelleFile(cf.customBgmFile)
    }
    if (cf.bgmMode !== 'none') payload.bgm_volume = cf.bgmVolume

    if (vf.refAudioFile) {
      progress.value.message = '正在上传参考音频...'
      const refAudioPath = await uploadPixelleFile(vf.refAudioFile)
      payload.ref_audio_path = refAudioPath
      payload.reference_audio_path = refAudioPath
    }

    // Character & scene references
    if (selectedCharacterIds.value.length) payload.character_ids = selectedCharacterIds.value
    if (selectedSceneIds.value.length) payload.scene_ids = selectedSceneIds.value

    // Per-layer model overrides
    const lm = layerModels.value
    if (lm.scriptLLM && lm.scriptLLM !== 'qwen-max') payload.script_llm = lm.scriptLLM
    if (lm.imageModel && lm.imageModel !== 'auto') payload.image_model = lm.imageModel
    if (lm.videoModel && lm.videoModel !== 'auto') payload.video_model = lm.videoModel
    if (lm.ttsModel && lm.ttsModel !== 'edge-tts') payload.tts_model = lm.ttsModel
    if (lm.auditModel && lm.auditModel !== 'auto') payload.audit_model = lm.auditModel

    const sc = systemConfig.value
    if (sc.templateFontSize || sc.templateTextColor || sc.templateBgColor) {
      payload.template_params = {}
      if (sc.templateFontSize) payload.template_params.font_size = sc.templateFontSize
      if (sc.templateTextColor) payload.template_params.text_color = sc.templateTextColor
      if (sc.templateBgColor) payload.template_params.background_color = sc.templateBgColor
    }

    progress.value.message = '正在提交任务...'
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('未获取到 Pixelle 任务 ID')

    progress.value.message = 'AI 正在生成脚本...'
    progress.value.percent = 5
    await pollTask(taskId, payload.video_model)

  } catch (e) {
    const errMsg = e.response?.data?.detail || e.message || '视频生成失败'
    result.value = { success: false, error: errMsg }
    history.value.unshift({ text: cf.text, success: false })
    toast.error(errMsg)
  } finally {
    generating.value = false
    clearPoll()
  }
}

// 前端业务函数：协调 pollTask 对应的页面流程、接口调用或状态转换。
// 入参：taskId、videoModel 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 pollTask 对应业务流程的处理结果。
function pollTask(taskId, videoModel = 'auto') {
  const maxAttempts = videoModel === 'seedance' ? 180 : videoModel === 'kling' ? 120 : 120
  return new Promise((resolve, reject) => {
    let attempts = 0
    pollTimer = setInterval(async () => {
      attempts++
      if (attempts > maxAttempts) { reject(new Error(`视频生成超时 (${(maxAttempts * 5 / 60).toFixed(0)}min)`)); return }
      try {
        const resp = await getTask(taskId)
        const data = resp.data
        if (data.status === 'completed') {
          clearPoll()
          videoUrl.value = getVideoFileUrl(data.video_path)
          result.value = { success: true, taskId, duration: data.duration, fileSize: data.file_size, frames: data.frames, videoPath: data.video_path }
          history.value.unshift({ text: contentForm.value.text, success: true })
          toast.success('视频生成完成！')
          resolve()
        } else if (data.status === 'failed') {
          reject(new Error(data.error || 'Pixelle-Video 返回失败'))
        } else {
          const stageMap = {
            narrating: '分镜脚本生成中...',
            generating_images: '画面渲染中...',
            generating_video: '视频画面生成中...',
            tts: 'TTS 配音合成中...',
            composing: 'FFmpeg 最终合成中...',
          }
          const pct = data.progress != null ? Math.min(95, data.progress) : Math.min(95, progress.value.percent + 0.3)
          const stage = data.stage || ''
          const stageMsg = stageMap[stage] || `处理中 (${data.status})`

          // Show frame progress: "分镜 3/5 — 步骤 2/4: 生成插图"
          const frame = data.current_frame
          const total = data.total_frames
          if (frame && total) {
            progress.value.message = `分镜 ${frame}/${total} — ${stageMsg}`
          } else {
            progress.value.message = stageMsg
          }
          progress.value.percent = pct
        }
      } catch {
        if (attempts % 6 === 0) progress.value.message = `网络波动，重试中... (${attempts}/120)`
      }
    }, 5000)
  })
}

// 前端业务函数：协调 clearPoll 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 clearPoll 对应业务流程的处理结果。
function clearPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// 前端业务函数：协调 handleClearResult 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleClearResult 对应业务流程的处理结果。
function handleClearResult() {
  result.value = null
  videoUrl.value = ''
  progress.value = { percent: 0, message: '', status: '' }
}

// ==================== Lifecycle ====================

// Two-way sync: layerModels ↔ voiceVisualForm
watch(() => layerModels.value.ttsModel, (val) => {
  if (voiceVisualForm.value.ttsEngine !== val) {
    voiceVisualForm.value = { ...voiceVisualForm.value, ttsEngine: val }
  }
})
watch(() => voiceVisualForm.value.ttsEngine, (val) => {
  if (layerModels.value.ttsModel !== val) {
    layerModels.value = { ...layerModels.value, ttsModel: val }
  }
})
watch(() => layerModels.value.imageModel, (val) => {
  const wf = val === 'flux' ? 'runninghub/image_flux.json' : val === 'sdxl' ? 'comfyui/sdxl.json' : ''
  if (voiceVisualForm.value.mediaWorkflow !== wf) {
    voiceVisualForm.value = { ...voiceVisualForm.value, mediaWorkflow: wf }
  }
})

onMounted(() => { loadSystemConfig(); fetchResources(); loadAssets() })
onUnmounted(() => { clearPoll() })
</script>

<template>
  <div class="max-w-[1440px] mx-auto px-4">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold gradient-text">AI 视频工坊</h1>
      <span class="text-xs text-slate-500">Pixelle-Video</span>
    </div>

    <!-- Pipeline tabs -->
    <div class="flex flex-wrap gap-1.5 mb-4">
      <button v-for="p in pipelines" :key="p.key" @click="activePipeline = p.key"
        class="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all"
        :class="activePipeline === p.key ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'"
        :title="p.desc">
        <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="p.icon"/></svg>
        {{ p.label }}
      </button>
    </div>

    <SystemConfigPanel
      v-model="systemConfig"
      @test-connection="handleTestConnection"
    />

    <!-- Standard pipeline (quick_create) -->
    <div v-if="activePipeline === 'quick_create'" class="space-y-4" style="min-height: calc(100vh - 330px);">
      <!-- Per-layer model config -->
      <PipelineLayerConfig v-model="layerModels" />
      <!-- Character & scene selection chips -->
      <div v-if="characterList.length || sceneList.length" class="flex gap-4 flex-wrap">
        <div v-if="characterList.length" class="flex-1 min-w-0">
          <label class="block text-xs text-slate-400 mb-1.5">选择角色 (可多选)</label>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="c in characterList" :key="c.id" @click="toggleCharacter(c.id)"
              class="px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer"
              :class="selectedCharacterIds.includes(c.id) ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
              {{ c.name }}
            </button>
          </div>
        </div>
        <div v-if="sceneList.length" class="flex-1 min-w-0">
          <label class="block text-xs text-slate-400 mb-1.5">选择场景 (可多选)</label>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="s in sceneList" :key="s.id" @click="toggleScene(s.id)"
              class="px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer"
              :class="selectedSceneIds.includes(s.id) ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
              {{ s.name }}
            </button>
          </div>
        </div>
      </div>
      <!-- Three-column layout -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ContentPanel v-model="contentForm" :bgm-list="bgmList" @bgm-upload="handleBgmUpload"/>
        <VoiceVisualPanel v-model="voiceVisualForm" :templates="templates" :media-workflows="mediaWorkflows" :tts-workflows="ttsWorkflows" :resources-loading="resourcesLoading" @ref-audio-upload="handleRefAudioUpload"/>
        <GeneratePanel :generating="generating" :progress="progress" :result="result" :history="history" :video-url="videoUrl" :config-valid="!!(systemConfig.llmApiKey || systemConfig.runninghubApiKey)" @generate="handleGenerate" @clear-result="handleClearResult"/>
      </div>
    </div>

    <!-- Custom Media -->
    <CustomMediaPanel v-else-if="activePipeline === 'custom_media'" />

    <!-- Digital Human -->
    <DigitalHumanPanel v-else-if="activePipeline === 'digital_human'" />

    <!-- Image to Video -->
    <ImageToVideoPanel v-else-if="activePipeline === 'image_to_video'" />

    <!-- Action Transfer -->
    <ActionTransferPanel v-else-if="activePipeline === 'action_transfer'" />

    <!-- Seedance 2.0 -->
    <SeedancePanel v-else-if="activePipeline === 'seedance'" />
  </div>
</template>
