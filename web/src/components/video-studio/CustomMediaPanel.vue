<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { ref } from 'vue'
import { runPixelleVideoGeneration, uploadPixelleFiles } from './pixelleGeneration.js'

const emit = defineEmits(['generate-start', 'generate-result'])

// Left: Asset input
const assetFiles = ref([])
const assetPreviews = ref([])
const videoTitle = ref('')
const videoText = ref('')

// Middle: Video config
const ttsVoice = ref('zh-CN-XiaoxiaoNeural')
const mediaWorkflow = ref('')

// BGM
const bgmPath = ref('')
const bgmVolume = ref(0.2)

// Right: Output
const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)
const videoUrl = ref('')

// 前端业务函数：协调 handleFiles 对应的页面流程、接口调用或状态转换。
function handleFiles(e) {
  const files = Array.from(e.target.files || [])
  assetFiles.value = files
  assetPreviews.value = files.map(f => URL.createObjectURL(f))
}

// 前端业务函数：协调 handleGenerate 对应的页面流程、接口调用或状态转换。
async function handleGenerate() {
  if (assetFiles.value.length === 0) return
  generating.value = true; result.value = null; videoUrl.value = ''
  progress.value = { percent: 0, message: '正在上传素材...' }
  try {
    const assetPaths = await uploadPixelleFiles(assetFiles.value)
    const payload = {
      text: videoText.value || 'generated video',
      mode: 'generate',
      n_scenes: 1,
      tts_voice: ttsVoice.value,
      bgm_volume: bgmVolume.value,
      asset_paths: assetPaths,
      media_paths: assetPaths,
    }
    if (videoTitle.value) payload.title = videoTitle.value
    if (mediaWorkflow.value) payload.media_workflow = mediaWorkflow.value
    if (bgmPath.value) payload.bgm_path = bgmPath.value

    progress.value = { percent: 2, message: '正在提交任务...' }
    const done = await runPixelleVideoGeneration(payload, {
      onProgress: (p) => {
        progress.value = {
          percent: p.percent ?? Math.min(95, progress.value.percent + 0.5),
          message: p.message,
        }
      },
    })
    result.value = done
    videoUrl.value = done.videoUrl
  } catch (e) {
    result.value = { success: false, error: e.message }
  } finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Asset Upload -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">素材上传</h3>
      <div class="mb-4">
        <label class="block text-xs text-slate-400 mb-1.5">选择图片/视频/音频</label>
        <input type="file" multiple accept="image/*,video/*,audio/*" @change="handleFiles"
          class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-purple-500/20 file:text-purple-300 file:border-0"/>
      </div>
      <div v-if="assetPreviews.length" class="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
        <div v-for="(url, i) in assetPreviews" :key="i" class="rounded-lg overflow-hidden bg-slate-800">
          <img v-if="assetFiles[i]?.type?.startsWith('image')" :src="url" class="w-full h-20 object-cover"/>
          <video v-else-if="assetFiles[i]?.type?.startsWith('video')" :src="url" class="w-full h-20 object-cover"/>
          <div v-else class="text-xs text-slate-400 p-2 truncate">{{ assetFiles[i]?.name }}</div>
        </div>
      </div>
      <p class="text-[11px] text-slate-500 mt-2">上传您的素材文件，Pixelle-Video 将基于它们生成视频</p>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">视频配置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">配音角色</label>
          <select v-model="ttsVoice" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="zh-CN-XiaoxiaoNeural">晓晓 (女)</option>
            <option value="zh-CN-YunxiNeural">云希 (男)</option>
            <option value="zh-CN-XiaoyiNeural">晓伊 (女)</option>
            <option value="zh-CN-YunjianNeural">云健 (男)</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">BGM 音量</label>
          <input type="range" min="0" max="0.5" step="0.01" v-model.number="bgmVolume" class="w-full accent-purple-500"/>
          <span class="text-[11px] text-slate-500">{{ bgmVolume.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成视频</h3>
      <button @click="handleGenerate" :disabled="generating || assetFiles.length === 0"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400'">
        {{ generating ? '生成中...' : '生成视频' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="mb-4">
        <div class="text-xs text-emerald-400 mb-2">生成完成!</div>
        <video v-if="videoUrl" :src="videoUrl" controls class="w-full rounded-lg" style="max-height:260px"/>
        <a v-if="videoUrl" :href="videoUrl" download class="mt-2 inline-flex text-xs text-cyan-300 hover:text-cyan-200">下载视频</a>
        <div v-else class="text-xs text-amber-300">任务已完成，但未返回视频路径</div>
      </div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
