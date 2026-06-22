<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { ref } from 'vue'
import { renderFrame, synthesizeTTS, generateImage } from '../../api/pixelle-client.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
  templates: { type: Array, default: () => [] },
  mediaWorkflows: { type: Array, default: () => [] },
  ttsWorkflows: { type: Array, default: () => [] },
  resourcesLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'ref-audio-upload'])

const templateTab = ref('1080x1920')
const templateType = ref('image')

const templateResolutions = [
  { key: '1080x1920', label: '竖屏 9:16 (抖音)' },
  { key: '1920x1080', label: '横屏 16:9' },
  { key: '1080x1080', label: '方形 1:1' },
]
const templateTypes = [
  { key: 'static', label: '静态', hint: '纯文字模板，无需AI配图' },
  { key: 'image', label: '配图', hint: '需要AI生成配图' },
  { key: 'video', label: '视频', hint: '需要AI生成视频画面' },
]

// 入参：key、value 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateField 对应业务流程的处理结果。
function updateField(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const edgeTtsVoices = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓 (女)', gender: 'female' },
  { id: 'zh-CN-YunxiNeural', name: '云希 (男)', gender: 'male' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊 (女)', gender: 'female' },
  { id: 'zh-CN-YunjianNeural', name: '云健 (男)', gender: 'male' },
  { id: 'zh-CN-XiaobeiNeural', name: '晓北 (女)', gender: 'female' },
  { id: 'zh-CN-YunyangNeural', name: '云扬 (男)', gender: 'male' },
  { id: 'zh-CN-XiaohanNeural', name: '晓涵 (女)', gender: 'female' },
  { id: 'en-US-GuyNeural', name: 'Guy (男-英文)', gender: 'male' },
  { id: 'en-US-JennyNeural', name: 'Jenny (女-英文)', gender: 'female' },
]

const ttsEngines = [
  { value: 'edge-tts', label: 'Edge-TTS', desc: '免费在线引擎' },
  { value: 'index-tts', label: 'Index-TTS', desc: '声音克隆' },
  { value: 'spark-tts', label: 'Spark-TTS', desc: '高级合成' },
  { value: 'custom', label: '自定义 ComfyUI', desc: '自托管工作流' },
]

// TTS preview
const showTTSPreview = ref(false)
const ttsPreviewText = ref('大家好，这是一段测试语音。')
const ttsPreviewLoading = ref(false)
const ttsPreviewAudio = ref('')

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleTTSPreview 对应业务流程的处理结果。
async function handleTTSPreview() {
  ttsPreviewLoading.value = true
  ttsPreviewAudio.value = ''
  try {
    const resp = await synthesizeTTS({
      text: ttsPreviewText.value,
      mode: props.modelValue.ttsEngine === 'comfyui' ? 'comfyui' : 'edge',
      voice: props.modelValue.ttsVoice,
      speed: props.modelValue.ttsSpeed || 1.0,
    })
    // TTS API returns audio path; build URL through proxy
    const data = resp.data
    if (data.audio_path) {
      const p = (data.audio_path || '').replace(/\\/g, '/')
      const rel = p.replace(/^.*\/Pixelle-Video\//, '')
      ttsPreviewAudio.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(rel)}`
    }
  } catch { /* preview failed */ }
  finally { ttsPreviewLoading.value = false }
}

// 前端业务函数：协调 getTemplatePreviewUrl 对应的页面流程、接口调用或状态转换。
// 入参：tpl 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getTemplatePreviewUrl 对应业务流程的处理结果。
function getTemplatePreviewUrl(tpl) {
  const key = (tpl.key || tpl.path || tpl.name || '').replace(/\\/g, '/')
  const parts = key.split('/')
  if (parts.length >= 2) {
    const size = parts[0]
    const tplName = parts[1].replace('.html', '')
    const token = localStorage.getItem('token') || ''
    return `/api/pixelle/template-preview/${size}/${tplName}.jpg?token=${encodeURIComponent(token)}`
  }
  return ''
}

// 前端业务函数：协调 isSelected 对应的页面流程、接口调用或状态转换。
// 入参：tpl 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 isSelected 对应业务流程的处理结果。
function isSelected(tpl) {
  return (props.modelValue.frameTemplate || '') === (tpl.key || tpl.path || tpl.name)
}

// 前端业务函数：协调 filteredTemplates 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 filteredTemplates 对应业务流程的处理结果。
function filteredTemplates() {
  let list = props.templates || []
  list = list.filter(t => {
    const key = t.key || t.path || t.name || ''
    return key.includes(templateTab.value)
  })
  if (templateType.value !== 'all') {
    list = list.filter(t => {
      const name = (t.name || t.key || '').toLowerCase()
      return name.includes(templateType.value + '_') || name.startsWith(templateType.value)
    })
  }
  return list
}

// Template preview lightbox
const previewTemplate = ref(null)
const previewImage = ref('')
const previewLoading = ref(false)
const showPreview = ref(false)
const previewRenderText = ref('AI 视频工坊')

// 入参：tpl 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 openRenderPreview 对应业务流程的处理结果。
function openRenderPreview(tpl) {
  if (tpl) {
    previewTemplate.value = tpl
  } else if (props.modelValue.frameTemplate) {
    previewTemplate.value = (props.templates || []).find(
      t => (t.key || t.path || t.name) === props.modelValue.frameTemplate
    ) || null
  }
  showPreview.value = true
  if (previewTemplate.value) {
    previewImage.value = getTemplatePreviewUrl(previewTemplate.value)
  }
}

// 前端业务函数：协调 handlePlaywrightRender 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handlePlaywrightRender 对应业务流程的处理结果。
async function handlePlaywrightRender() {
  previewLoading.value = true
  try {
    const key = (previewTemplate.value?.key || previewTemplate.value?.path || previewTemplate.value?.name || '')
    const resp = await renderFrame(key, previewRenderText.value || '预览')
    const data = resp.data
    if (data.frame_path) {
      const p = data.frame_path.replace(/\\/g, '/')
      const rel = p.replace(/^.*\/Pixelle-Video\//, '')
      previewImage.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(rel)}`
    }
  } catch { /* keep static preview */ }
  finally { previewLoading.value = false }
}

// 前端业务函数：协调 closePreview 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 closePreview 对应业务流程的处理结果。
function closePreview() {
  showPreview.value = false
  previewTemplate.value = null
  previewImage.value = ''
}

// 前端业务函数：协调 getTemplateSize 对应的页面流程、接口调用或状态转换。
// 入参：tplPath 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 getTemplateSize 对应业务流程的处理结果。
function getTemplateSize(tplPath) {
  if (!tplPath) return ''
  const key = tplPath.replace(/\\/g, '/')
  if (key.includes('1080x1920')) return '1080 × 1920 (竖屏 9:16)'
  if (key.includes('1920x1080')) return '1920 × 1080 (横屏 16:9)'
  if (key.includes('1080x1080')) return '1080 × 1080 (方形 1:1)'
  return ''
}

// Media preview
const showMediaPreview = ref(false)
const mediaPreviewLoading = ref(false)
const mediaPreviewUrl = ref('')
const mediaPreviewPrompt = ref('')

// 前端业务函数：协调 handleMediaPreview 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleMediaPreview 对应业务流程的处理结果。
async function handleMediaPreview() {
  mediaPreviewLoading.value = true
  mediaPreviewUrl.value = ''
  try {
    const resp = await generateImage({
      prompt: mediaPreviewPrompt.value || 'a beautiful landscape',
      workflow: props.modelValue.mediaWorkflow || undefined,
    })
    const data = resp.data
    if (data.url) {
      mediaPreviewUrl.value = data.url
    } else if (data.image_path) {
      const p = (data.image_path || '').replace(/\\/g, '/')
      const rel = p.replace(/^.*\/Pixelle-Video\//, '')
      mediaPreviewUrl.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(rel)}`
    }
  } catch { mediaPreviewUrl.value = '' }
  finally { mediaPreviewLoading.value = false }
}
</script>

<template>
  <div class="glass-card p-5 h-full overflow-y-auto">
    <div class="flex items-center gap-2 mb-5">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
        </svg>
      </div>
      <h3 class="text-sm font-semibold text-white">声音 & 视觉</h3>
    </div>

    <!-- TTS Engine -->
    <div class="mb-5">
      <label class="block text-xs text-slate-400 mb-2">TTS 语音引擎</label>
      <div class="grid grid-cols-2 gap-1.5">
        <button
          v-for="eng in ttsEngines" :key="eng.value"
          @click="updateField('ttsEngine', eng.value)"
          class="text-left px-3 py-2 rounded-lg text-xs transition-all"
          :class="modelValue.ttsEngine === eng.value
            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
            : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'"
        >
          <div class="font-medium">{{ eng.label }}</div>
          <div class="text-[11px] opacity-60">{{ eng.desc }}</div>
        </button>
      </div>
    </div>

    <!-- Voice selector (Edge-TTS) -->
    <div v-if="modelValue.ttsEngine === 'edge-tts'" class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">语音角色</label>
      <select
        :value="modelValue.ttsVoice"
        @change="updateField('ttsVoice', $event.target.value)"
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-purple-500/50"
      >
        <option v-for="v in edgeTtsVoices" :key="v.id" :value="v.id">{{ v.name }}</option>
      </select>
      <!-- Speed slider -->
      <label class="block text-xs text-slate-400 mt-3 mb-1">语速: <span class="text-white font-semibold">{{ (modelValue.ttsSpeed || 1.0).toFixed(1) }}x</span></label>
      <input type="range" min="0.5" max="2.0" step="0.1" :value="modelValue.ttsSpeed || 1.0"
        @input="updateField('ttsSpeed', Number($event.target.value))" class="w-full accent-purple-500"/>
    </div>

    <!-- TTS Preview -->
    <div class="mb-5 border-t border-white/5 pt-3">
      <button type="button" @click="showTTSPreview = !showTTSPreview"
        class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">
        <svg class="w-3 h-3 transition-transform" :class="showTTSPreview ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        语音试听
      </button>
      <div v-if="showTTSPreview" class="mt-2 space-y-2">
        <input v-model="ttsPreviewText" type="text" placeholder="输入试听文字..."
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500"/>
        <button @click="handleTTSPreview" :disabled="ttsPreviewLoading"
          class="w-full px-3 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 disabled:opacity-50">
          {{ ttsPreviewLoading ? '生成中...' : '试听' }}
        </button>
        <audio v-if="ttsPreviewAudio" :src="ttsPreviewAudio" controls class="w-full h-7" controlslist="nodownload"/>
      </div>
    </div>

    <!-- Voice cloning (Index-TTS) -->
    <div v-if="modelValue.ttsEngine === 'index-tts'" class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">参考音频（声音克隆）</label>
      <input type="file" accept=".mp3,.wav,.flac" @change="$emit('ref-audio-upload', $event)" class="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:text-xs file:bg-purple-500/20 file:text-purple-300 file:border-0 hover:file:bg-purple-500/30"/>
      <p class="text-[11px] text-slate-500 mt-1">上传一个人的声音样本（10-30 秒），AI 将模仿其声音</p>
    </div>

    <!-- Custom TTS workflow -->
    <div v-if="modelValue.ttsEngine === 'custom'" class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">TTS 工作流路径</label>
      <input
        :value="modelValue.ttsWorkflow"
        @input="updateField('ttsWorkflow', $event.target.value)"
        placeholder="selfhost/tts_edge.json"
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
      />
    </div>

    <!-- Media Workflow -->
    <div class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">画面/视频生成引擎</label>
      <select
        :value="modelValue.mediaWorkflow"
        @change="updateField('mediaWorkflow', $event.target.value)"
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-purple-500/50"
      >
        <option value="">使用系统默认</option>
        <option v-for="wf in mediaWorkflows" :key="wf.key" :value="wf.key">
          {{ wf.display_name || wf.name }}
        </option>
      </select>
    </div>

    <!-- Prompt Prefix -->
    <div class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">画面风格提示词</label>
      <input
        :value="modelValue.promptPrefix"
        @input="updateField('promptPrefix', $event.target.value)"
        placeholder="例如：极简黑白火柴人风格、中国水墨画风..."
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
      />
    </div>

    <!-- Media Preview expander -->
    <div class="border-t border-white/5 pt-4 mb-5">
      <button type="button" @click="showMediaPreview = !showMediaPreview"
        class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">
        <svg class="w-3 h-3 transition-transform" :class="showMediaPreview ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        媒体预览（生成引擎测试）
      </button>
      <div v-if="showMediaPreview" class="mt-2 space-y-2">
        <input v-model="mediaPreviewPrompt" type="text" placeholder="输入测试 prompt..."
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500"/>
        <button @click="handleMediaPreview" :disabled="mediaPreviewLoading"
          class="w-full px-3 py-2 rounded-lg bg-pink-500/20 text-pink-300 text-xs hover:bg-pink-500/30 disabled:opacity-50">
          {{ mediaPreviewLoading ? '生成中...' : '生成预览' }}
        </button>
        <div v-if="mediaPreviewUrl" class="rounded-lg overflow-hidden bg-slate-900">
          <img v-if="mediaPreviewUrl" :src="mediaPreviewUrl" class="w-full max-h-48 object-contain"/>
        </div>
      </div>
    </div>

    <!-- Template Browser -->
    <div class="border-t border-white/5 pt-4">
      <label class="block text-xs text-slate-400 mb-2">画面模板</label>

      <!-- Type selector -->
      <div class="flex gap-1 mb-2">
        <button
          v-for="t in templateTypes" :key="t.key"
          @click="templateType = t.key"
          class="flex-1 px-2 py-1.5 rounded text-[11px] transition-all"
          :class="templateType === t.key ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-300'"
          :title="t.hint"
        >{{ t.label }}</button>
      </div>

      <!-- Resolution tabs -->
      <div class="flex gap-1 mb-3">
        <button
          v-for="res in templateResolutions" :key="res.key"
          @click="templateTab = res.key"
          class="flex-1 px-2 py-1.5 rounded text-[11px] font-medium transition-all"
          :class="templateTab === res.key ? 'bg-purple-500/20 text-purple-300' : 'bg-white/5 text-slate-400 hover:text-slate-300'"
        >{{ res.label }}</button>
      </div>

      <!-- Template grid with preview images -->
      <div v-if="resourcesLoading" class="text-xs text-slate-500 py-4 text-center">加载资源中...</div>
      <div v-else-if="filteredTemplates().length > 0" class="grid grid-cols-3 gap-2 max-h-72 overflow-y-auto pr-1">
        <div
          v-for="tpl in filteredTemplates()" :key="tpl.key || tpl.path || tpl.name"
          class="group rounded-lg transition-all overflow-hidden cursor-pointer"
          :class="isSelected(tpl) ? 'ring-2 ring-purple-400/60' : 'hover:ring-1 hover:ring-white/20'"
        >
          <!-- Preview image -->
          <div class="relative bg-slate-800 overflow-hidden" style="aspect-ratio: 9/16">
            <!-- Fallback behind image -->
            <div class="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-slate-700 to-slate-900 text-slate-600 z-0">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
            </div>
            <!-- Preview image on top -->
            <img
              :src="getTemplatePreviewUrl(tpl)"
              class="absolute inset-0 w-full h-full object-cover z-[1]"
              :alt="tpl.display_name || tpl.name"
              @error="$event.target.style.display='none'"
              @click="openRenderPreview(tpl)"
            />
            <!-- Selected check -->
            <div v-if="isSelected(tpl)" class="absolute top-1 right-1 w-4 h-4 rounded-full bg-purple-500 flex items-center justify-center z-10">
              <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
              </svg>
            </div>
          </div>
          <!-- Name + select button -->
          <div class="px-1.5 py-1">
            <p class="text-[10px] text-slate-400 truncate mb-1">{{ tpl.display_name || tpl.name || tpl.key }}</p>
            <button
              @click="updateField('frameTemplate', tpl.key || tpl.path || tpl.name)"
              class="w-full px-2 py-1 rounded text-[11px] font-medium transition-all"
              :class="isSelected(tpl) ? 'bg-purple-500/20 text-purple-300' : 'bg-white/5 text-slate-400 hover:bg-white/10'"
            >
              {{ isSelected(tpl) ? '已选中' : '选择' }}
            </button>
          </div>
        </div>
      </div>
      <div v-else class="text-xs text-slate-500 py-4 text-center">
        暂无模板
      </div>

      <!-- Selected template info + preview + media size -->
      <div v-if="modelValue.frameTemplate" class="mt-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-xs text-slate-300">已选: <span class="text-white text-[11px]">{{ modelValue.frameTemplate }}</span></span>
          <button @click="openRenderPreview()" class="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
            </svg>
            渲染预览
          </button>
        </div>
        <!-- Media size info -->
        <div class="text-[11px] text-slate-400 flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/></svg>
          <span>模板尺寸: <span class="text-slate-300">{{ getTemplateSize(modelValue.frameTemplate) }}</span></span>
        </div>
      </div>
    </div>

    <!-- Render Preview Lightbox -->
    <Teleport to="body">
      <div v-if="showPreview" class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm" @click.self="closePreview">
        <div class="w-full max-w-lg mx-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-white text-sm font-medium">{{ modelValue.frameTemplate || '模板渲染预览' }}</span>
            <button @click="closePreview" class="text-slate-400 hover:text-white transition-colors">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="space-y-2 mb-3">
            <input v-model="previewRenderText" type="text" placeholder="预览文字..." class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500"/>
            <button @click="handlePlaywrightRender" :disabled="previewLoading" class="w-full px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 disabled:opacity-50">
              {{ previewLoading ? '渲染中...' : '重新渲染' }}
            </button>
          </div>
          <div class="rounded-lg overflow-hidden bg-slate-900 flex items-center justify-center min-h-[300px]">
            <div v-if="previewLoading" class="flex items-center gap-2 text-slate-400 py-16">
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" class="opacity-25"/>
                <path stroke-linecap="round" stroke-width="3" d="M12 2a10 10 0 019.95 9" fill="currentColor"/>
              </svg>
              <span class="text-sm">正在渲染模板预览...</span>
            </div>
            <img v-else-if="previewImage" :src="previewImage" class="w-full object-contain max-h-[70vh]"/>
            <div v-else class="text-slate-500 text-sm py-16">渲染失败</div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
