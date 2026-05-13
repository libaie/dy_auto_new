<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const imageFiles = ref([])
const imagePreviews = ref([])
const promptText = ref('')
const mediaWorkflow = ref('')
const videoDuration = ref(5)

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)

function handleImages(e) {
  const files = Array.from(e.target.files || [])
  imageFiles.value = files
  imagePreviews.value = files.map(f => URL.createObjectURL(f))
}

async function handleGenerate() {
  if (imageFiles.value.length === 0) return
  generating.value = true; result.value = null
  try {
    const payload = {
      text: promptText.value || 'animated scene',
      mode: 'generate',
      n_scenes: 1,
    }
    if (mediaWorkflow.value) payload.media_workflow = mediaWorkflow.value
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('No task ID')
    await new Promise((resolve, reject) => {
      let a = 0; const t = setInterval(async () => {
        a++; if (a > 120) { clearInterval(t); reject(new Error('Timeout')); return }
        try {
          const r = await getTask(taskId)
          if (r.data.status === 'completed') { clearInterval(t); result.value = { success: true, taskId }; resolve() }
          else if (r.data.status === 'failed') { clearInterval(t); reject(new Error(r.data.error)) }
          else { progress.value.percent = Math.min(95, r.data.progress || progress.value.percent + 0.5); progress.value.message = r.data.status }
        } catch {}
      }, 5000)
    })
  } catch (e) { result.value = { success: false, error: e.message } }
  finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Image Upload -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">上传图片/视频</h3>
      <input type="file" multiple accept="image/*,video/*" @change="handleImages"
        class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-orange-500/20 file:text-orange-300 file:border-0"/>
      <div v-if="imagePreviews.length" class="grid grid-cols-2 gap-2 mt-3 max-h-40 overflow-y-auto">
        <div v-for="(url, i) in imagePreviews" :key="i" class="rounded-lg overflow-hidden bg-slate-800">
          <img v-if="imageFiles[i]?.type?.startsWith('image')" :src="url" class="w-full h-24 object-cover"/>
          <video v-else :src="url" class="w-full h-24 object-cover"/>
        </div>
      </div>
      <p class="text-[11px] text-slate-500 mt-2">上传静态图片或视频片段，AI 将基于素材生成动态视频</p>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">生成配置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">描述文本</label>
          <textarea v-model="promptText" rows="3" placeholder="描述您想要的视频效果..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">视频时长: {{ videoDuration }}s</label>
          <input type="range" min="2" max="15" v-model.number="videoDuration" class="w-full accent-orange-500"/>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成视频</h3>
      <button @click="handleGenerate" :disabled="generating || imageFiles.length === 0"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-400 hover:to-red-400'">
        {{ generating ? '生成中...' : '开始生成' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-orange-500 to-red-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
