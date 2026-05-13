<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const sourceVideo = ref(null)
const sourcePreview = ref('')
const actionPrompt = ref('')
const transferWorkflow = ref('')

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)

function handleVideo(e) {
  const file = e.target.files?.[0]
  if (file) {
    sourceVideo.value = file
    sourcePreview.value = URL.createObjectURL(file)
  }
}

async function handleGenerate() {
  if (!sourceVideo.value) return
  generating.value = true; result.value = null
  try {
    const payload = {
      text: actionPrompt.value || 'action transfer',
      mode: 'generate',
      n_scenes: 1,
    }
    if (transferWorkflow.value) payload.media_workflow = transferWorkflow.value
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
    <!-- Left: Video Upload -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">上传源视频</h3>
      <input type="file" accept="video/*" @change="handleVideo"
        class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-pink-500/20 file:text-pink-300 file:border-0"/>
      <div v-if="sourcePreview" class="mt-3 rounded-lg overflow-hidden bg-slate-800">
        <video :src="sourcePreview" class="w-full max-h-40 object-cover" controls/>
      </div>
      <p class="text-[11px] text-slate-500 mt-2">上传一段视频作为动作源，AI 将提取动作并迁移</p>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">迁移配置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">动作描述</label>
          <textarea v-model="actionPrompt" rows="3" placeholder="描述您想要的动作效果..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">迁移工作流</label>
          <select v-model="transferWorkflow" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="">默认工作流</option>
            <option value="runninghub/af_scail.json">AF Scail — Runninghub</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成视频</h3>
      <button @click="handleGenerate" :disabled="generating || !sourceVideo"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-400 hover:to-rose-400'">
        {{ generating ? '生成中...' : '开始动作迁移' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-pink-500 to-rose-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
