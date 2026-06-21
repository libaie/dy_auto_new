<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { ref } from 'vue'
import { seedanceGenerate, seedanceGetTask } from '../../api/seedance-client.js'

const prompt = ref('')
const aspectRatio = ref('9:16')
const duration = ref(5)
const resolution = ref('720p')
const imageUrlText = ref('')

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)
const videoUrl = ref('')

const ratios = [
  { value: '9:16', label: '竖屏 9:16 (抖音)' },
  { value: '16:9', label: '横屏 16:9' },
  { value: '1:1', label: '方形 1:1' },
  { value: '3:4', label: '3:4' },
  { value: '4:3', label: '4:3' },
]

function imageUrls() {
  return imageUrlText.value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

async function handleGenerate() {
  if (!prompt.value.trim()) return

  generating.value = true
  result.value = null
  videoUrl.value = ''
  progress.value = { percent: 0, message: '正在提交 Seedance 任务...' }

  try {
    const payload = {
      prompt: prompt.value,
      aspect_ratio: aspectRatio.value,
      duration: duration.value,
      resolution: resolution.value,
      image_urls: imageUrls(),
    }

    const resp = await seedanceGenerate(payload)
    if (!resp.data?.ok) {
      throw new Error(resp.data?.error || '任务提交失败')
    }
    const taskId = resp.data.task_id
    if (!taskId) throw new Error('未获取到任务 ID')

    progress.value.message = 'Seedance 正在生成视频...'
    progress.value.percent = 5

    await new Promise((resolve, reject) => {
      let attempts = 0
      const t = setInterval(async () => {
        attempts++
        if (attempts > 180) { clearInterval(t); reject(new Error('生成超时 (15分钟)')); return }
        try {
          const r = await seedanceGetTask(taskId)
          const d = r.data
          if (d.status === 'succeeded') {
            clearInterval(t)
            videoUrl.value = d.video_url || ''
            result.value = { success: true, taskId }
            progress.value = { percent: 100, message: '生成完成！' }
            resolve()
          } else if (d.status === 'failed') {
            clearInterval(t)
            reject(new Error(d.error || '任务失败'))
          } else {
            const pct = d.progress != null ? Math.min(95, d.progress) : Math.min(95, progress.value.percent + 0.3)
            progress.value = { percent: pct, message: `生成中... (${d.status || 'running'})` }
          }
        } catch { /* 忽略单次轮询错误 */ }
      }, 5000)
    })
  } catch (e) {
    result.value = { success: false, error: e.message }
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Input -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">创作输入</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">视频描述 (Prompt)</label>
          <textarea v-model="prompt" rows="5"
            placeholder="描述你想要的视频内容，支持中文和英文..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">参考图片 URL (可选)</label>
          <textarea v-model="imageUrlText" rows="3" placeholder="每行一个可公网访问的图片 URL"
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
          <p class="text-[11px] text-slate-500 mt-1">Seedance 图生视频需要公网可访问的图片 URL</p>
        </div>
      </div>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">生成参数</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-slate-400 mb-1">画面比例</label>
          <div class="grid grid-cols-5 gap-1">
            <button v-for="r in ratios" :key="r.value" @click="aspectRatio = r.value"
              class="px-2 py-1.5 rounded text-[11px] font-medium transition-all"
              :class="aspectRatio === r.value ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
              {{ r.label }}
            </button>
          </div>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">时长: {{ duration }}s</label>
          <input type="range" min="4" max="15" v-model.number="duration" class="w-full accent-emerald-500"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">分辨率</label>
          <select v-model="resolution" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="480p">480p (标清)</option>
            <option value="720p">720p (高清)</option>
            <option value="1080p">1080p (全高清)</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">Seedance 2.0 生成</h3>
      <button @click="handleGenerate" :disabled="generating || !prompt.trim()"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400'">
        {{ generating ? '生成中...' : '开始生成' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="mb-4">
        <div class="text-xs text-emerald-400 mb-2">生成完成！</div>
        <video v-if="videoUrl" :src="videoUrl" controls class="w-full rounded-lg" style="max-height:260px"/>
      </div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
